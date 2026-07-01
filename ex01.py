"""
Quy tắc đúng của hệ thống:
- order_id phải tồn tại trong hệ thống. Nếu không tìm thấy, phải trả về
  404 Not Found.
- Khi lấy dữ liệu thành công, hệ thống trả về 200 OK.
- Vì lý do bảo mật, API công khai tuyệt đối không được lộ hai trường:
  profit_margin (biên lợi nhuận) và supplier_id (mã định danh nhà cung
  ứng nội bộ).

PHÂN TÍCH LỖI
BẢNG TEST CASE PHÁT HIỆN LỖI

STT | Dữ liệu gửi lên   | Kết quả hiện tại (Mã HTTP + Body)              | Kết quả đúng mong muốn                          | Lỗi phát hiện
----|-------------------|-------------------------------------------------|--------------------------------------------------|----------------------------------------------
1   | order_id = 999    | 200 OK                                          | 404 Not Found                                    | LỖI SAI STATUS CODE: Đơn hàng không tồn tại
    |                   | Body: {"message": "Order not found"}           | Body: {"detail": "Order not found"}             | nhưng hệ thống vẫn trả về 200 OK (thành công)
    |                   |                                                  |                                                  | kèm thông báo lỗi trong body. Client (đặc biệt
    |                   |                                                  |                                                  | là các hệ thống tự động/frontend) sẽ hiểu nhầm
    |                   |                                                  |                                                  | là request thành công, dẫn đến xử lý sai luồng.
----|-------------------|-------------------------------------------------|--------------------------------------------------|----------------------------------------------
2   | order_id = 1      | 200 OK                                          | 200 OK                                           | LỖI LỘ DỮ LIỆU NỘI BỘ (Sensitive Data Exposure):
    |                   | Body: {                                         | Body: {                                          | Hàm return order trả về toàn bộ dict lấy trực
    |                   |   "id": 1,                                      |   "id": 1,                                       | tiếp từ orders_db, bao gồm cả profit_margin
    |                   |   "customer_name": "Nguyen Van A",              |   "customer_name": "Nguyen Van A",               | (0.25) và supplier_id ("SUP_DELL_01"). Đây là
    |                   |   "total_amount": 1500000.0,                    |   "total_amount": 1500000.0                     | dữ liệu kinh doanh mật, không được phép để
    |                   |   "profit_margin": 0.25,   <-- LỘ MẬT           | }                                                 | khách hàng/đối thủ nhìn thấy qua API công khai.
    |                   |   "supplier_id": "SUP_DELL_01"  <-- LỘ MẬT      |                                                  | Nguyên nhân: không dùng response_model để lọc
    |                   | }                                                |                                                  | field, trả trực tiếp raw dict nội bộ ra ngoài.

TỔNG KẾT NGUYÊN NHÂN GỐC (ROOT CAUSE):
- Lỗi 1 (Status Code): Hàm xử lý khi không tìm thấy order chỉ return một
  dict thông thường (mặc định FastAPI trả 200 OK) thay vì raise
  HTTPException(status_code=404).
- Lỗi 2 (Lộ dữ liệu): Hàm return trực tiếp object "order" lấy từ
  orders_db (chứa toàn bộ field nội bộ) mà không đi qua một lớp
  response_model riêng (OrderPublic) chỉ khai báo các field được phép
  công khai. FastAPI chỉ tự động lọc field khi có response_model;
  nếu không có, mọi field trong dict trả về sẽ bị serialize hết ra JSON.

GIẢI PHÁP SỬA LỖI
- Tạo class OrderPublic (Pydantic) chỉ chứa các field công khai:
  id, customer_name, total_amount. KHÔNG có profit_margin, supplier_id.
- Gắn response_model=OrderPublic vào route -> FastAPI tự lọc bỏ field
  thừa dù hàm có return cả dict đầy đủ.
- Khi không tìm thấy order_id -> raise HTTPException(status_code=404,
  detail="Order not found") thay vì return dict với message thường.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

orders_db = [
    {
        "id": 1,
        "customer_name": "Nguyen Van A",
        "total_amount": 1500000.0,
        "profit_margin": 0.25,
        "supplier_id": "SUP_DELL_01",
    },
    {
        "id": 2,
        "customer_name": "Tran Thi B",
        "total_amount": 350000.0,
        "profit_margin": 0.30,
        "supplier_id": "SUP_LOGI_02",
    },
]


class OrderInternal(BaseModel):
    id: int
    customer_name: str
    total_amount: float
    profit_margin: float
    supplier_id: str


class OrderPublic(BaseModel):
    id: int
    customer_name: str
    total_amount: float


@app.get("/orders/{order_id}", response_model=OrderPublic)
def get_order_detail(order_id: int):
    for order in orders_db:
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found")
