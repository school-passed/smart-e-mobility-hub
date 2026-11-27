# Smart E-Mobility Hub — Hướng dẫn tích hợp theo source gốc

## 1. Trạng thái kiến trúc

Đây **đã là một modular monolith**: một `app.py`, một kho `shared/state.py` và sáu module gồm `service.py` / `ui.py`. Không tách thành sáu ứng dụng; không cần chuyển sang React, FastAPI, REST, message broker hoặc SQL cho bản MVP này.

## 2. Những thay đổi trong bản tích hợp đề xuất

- `app.py`: chuyển sidebar từ tên kỹ thuật SUB-01...SUB-06 sang **nghiệp vụ** theo vai trò. Giữ nguyên 6 module, không đổi UI ở sâu bên trong.
- `shared/auth.py`: tự đăng ký chỉ cho Student và Private EV Student; tài khoản Operator được cấp sẵn. Password trong demo vẫn là plaintext, chỉ được dùng trên máy cục bộ, không triển khai công khai.
- `shared/state.py`: khai báo đầy đủ `temporary_holds` và `shared_charging_requests` trong seed state.
- `modules/sub02/service.py`: yêu cầu sạc khi trả xe pin yếu chuyển sang `sub04.receive_shared_vehicle_charging_need`, thay vì ghi trực tiếp bản ghi thiếu `current_battery` vào `charging_requests`. Đồng thời yêu cầu Pickup Code hợp lệ, không chấp nhận chuỗi rỗng.
- `modules/sub05/service.py`: `expire_pending_reservations(get_state())` thay vì gọi thiếu tham số rồi bỏ qua lỗi.
- `modules/sub06/service.py`: snapshot lấy cả hai nguồn nhu cầu sạc (Private EV và shared EV), không đếm thiếu nhu cầu của xe dùng chung.
- `tests/test_workflows.py`: bốn bài kiểm thử xuyên SUB, kiểm tra quy tắc và trạng thái trên kho chung.

Không sửa các thuật toán mô phỏng, nghiệp vụ Operator confirm schedule hoặc biến đổi trạng thái xe CHARGING sau return — các quy tắc này cần nhóm duyệt đồng thời với việc chỉnh sửa Submission #1 nếu muốn thay đổi.

## 3. Chạy trên Windows PowerShell

```powershell
cd "D:\path\to\smart-e-mobility-hub-integrated"
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Tài khoản demo có sẵn

- `student` / `123`: Student (tìm/đặt/nhận/trả xe)
- `pstudent` / `123`: Private EV Student (đặt đỗ, gửi yêu cầu sạc)
- `operator` / `123`: Operator (sạc, vận hành, mô phỏng)

Lưu ý tài khoản demo và password đơn giản chỉ phục vụ bài tập lớn trên máy cục bộ.

## 4. Chạy kiểm thử service

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s modules/sub04 -p "test_*.py" -v
```

Các kiểm thử service không cần mở trình duyệt. Chúng **không thay thế** kiểm thử giao diện Streamlit; cần chạy UI trực tiếp trên máy có cài Streamlit.

## 5. Demo xuyên nghiệp vụ (cùng một server, dùng nhiều lần đăng nhập)

**Flow A — Shared vehicle**

1. Đăng nhập `student`; mở **Tìm kiếm & đặt xe**, chọn `HUB-01`, tạo reservation.
2. Mở **Nhận xe & trả xe**, chọn reservation và xe AVAILABLE, xác nhận pickup code.
3. Return tại `HUB-02` với pin `10%`; xem yêu cầu sạc tạo thành công.
4. Đăng xuất, đăng nhập `operator`; mở **Quản lý sạc** → `HUB-02` → **Hàng chờ ưu tiên**.
5. Chọn yêu cầu xe dùng chung thiếu giờ lấy xe, nhập departure time tương lai; xếp ưu tiên, đề xuất và xác nhận lịch.
6. Chuyển **Vận hành mạng lưới** để kiểm tra trạng thái xe và cổng sạc liên quan.

**Flow B — Private EV**

1. Đăng nhập `pstudent`, chọn ô có `has_charger = True` và `AVAILABLE`, giữ tạm 5 phút.
2. Xác nhận đặt chỗ; gửi ChargingRequest với giờ cần xe hợp lệ.
3. Đăng nhập `operator`, mở **Quản lý sạc**, xác nhận lịch rồi chuyển về tài khoản Student để kiểm tra trạng thái.

**Flow C — What-if**

1. Đăng nhập `operator`, mở **Mô phỏng What-if**.
2. Chọn `charging_pressure` tại Hub có request đang chờ, tạo snapshot, chạy scenario.
3. Đảm bảo mô phỏng không thay đổi dữ liệu hiện hành; chỉ đọc snapshot.

## 6. Những vấn đề còn cần quyết định trước khi nộp

1. `SUB-02` hiện chuyển xe pin yếu trực tiếp sang `CHARGING` trong khi yêu cầu sạc còn PENDING. Đó là logic bản gốc, chưa phản ánh thời điểm bắt đầu sạc vật lý; cần thống nhất với bản Submission #1 đã sửa nếu định điều chỉnh.
2. `SUB-05` ghi Incident nhưng chưa tự động đánh dấu tất cả tài nguyên là UNAVAILABLE hay liên động giải phóng/reschedule theo nghiệp vụ. Không nên trình diễn như một tính năng đã hoàn tất nếu chưa code.
3. Một số status trong seed data là `RESERVED`/`IN_USE` nhưng không có đủ bản ghi liên quan; chỉ là trạng thái mô phỏng, chưa phải dữ liệu vận hành nhất quán về lịch sử.
4. Bộ dữ liệu dùng chung trong Python là in-memory, mất khi restart; chưa đảm bảo an toàn ghi đồng thời. Chạy một Streamlit process cho MVP, không triển khai công khai.
5. `shared/auth.py` dùng mật khẩu plaintext, chưa phải hệ thống xác thực production.
6. SUB-06 hiện mới có 3 kịch bản; cần đối chiếu lại phạm vi thực hiện và kịch bản trong Submission #1.
7. README/PROJECT_TASKS gốc mang tính giai đoạn scaffold; cần cập nhật tiến độ và giới hạn thực tế khi nộp.

## 7. Thứ tự review PR theo phụ thuộc

| PR | Người phụ trách | Nội dung cần review | Reviewer liên SUB |
|---|---|---|---|
| INT-01 | Thành viên 1 | `app.py`, trạng thái dùng chung và trang tổng quan | Cả nhóm |
| INT-02 | Thành viên 2 & 4 | `SUB-02 → SUB-04` Shared EV Charging Request | M2/M4 |
| INT-03 | Thành viên 2 | Pickup Code validation | M1/M2 |
| INT-04 | Thành viên 5 & 1 | Expire reservation trong SUB-05 refresh | M1/M5 |
| INT-05 | Thành viên 6 & 4 | Snapshot gồm Shared EV charging demand | M4/M6 |
| INT-06 | Thành viên 2 | Sign Up giới hạn role | M2/M1 |
| INT-07 | Thành viên 6 | Unit/Integration test và báo cáo demo | Cả nhóm |

**Quy tắc**: không gộp tự động bản đề xuất vào `main` nếu chưa review và chạy thử UI; nên tạo branch `integration/mvp` từ source gốc, commit từng PR theo nội dung trên. Giữ nguyên source gốc như một mốc đối chứng.
