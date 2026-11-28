# Smart E-Mobility Hub — Final Integrated MVP

Hệ thống điều phối phương tiện điện cho Khu đô thị ĐHQG-HCM (**CO3001 — Công nghệ Phần mềm**), hợp nhất trọn vẹn chuẩn giao diện **Mobile App Sinh viên** (`feature/student-ui`), **Web Console Điều hành Operator** (`feature/operator-ui`) và toàn bộ nghiệp vụ tích hợp liên phân hệ (`SUB-01` đến `SUB-06`).

## 1. Kiến trúc & Giao diện thống nhất theo Submission #2

- **Giao diện Sinh viên (Mobile App Frame `440px` — Hình 49–54):**
  - Luồng xác thực 3 màn hình (`Welcome` → `Tạo tài khoản mới` / `Đăng nhập`) với mật khẩu băm `SHA-256`.
  - Thanh điều hướng 4 tab ở đáy: **📍 Khám phá** (`SUB-01`), **🔖 Của tôi** (`SUB-02`), **⚡ Đỗ & Sạc** (`SUB-03`) và **👤 Hồ sơ**.
- **Giao diện Nhân viên vận hành (Operator Desktop Console — Hình 55–65):**
  - Thanh Sidebar 7 chức năng kèm icon SVG & huy hiệu đếm sự cố đang mở: **Tổng quan mạng lưới**, **Điều chuyển xe**, **Giám sát tài nguyên sạc**, **Ưu tiên yêu cầu sạc**, **Lập lịch sạc**, **Sự cố**, **What-if Simulation**.
- **Nghiệp vụ lõi & Đồng bộ trạng thái (`shared/state.py` & `modules/sub01..06/service.py`):**
  - Bảo vệ nguyên tử bằng khóa đồng bộ `STATE_LOCK` / `@atomic`.
  - Tách biệt hoàn toàn dữ liệu vận hành (`_STORE`) và dữ liệu mô phỏng What-if (`_SANDBOX_STORE`).

## 2. Hướng dẫn chạy ứng dụng (Windows PowerShell)

```powershell
Set-Location C:\BachKhoa\Study\CNPM\smart-e-mobility-hub-git
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Tài khoản mẫu (Mật khẩu chung: `123`)
- **`student` / `123`** (`student@vnu.edu.vn`) — *Student*: Khám phá trạm, tìm xe, đặt giữ xe, quét nhận xe, báo lỗi đổi xe và trả xe (`SUB-01`, `SUB-02`).
- **`pstudent` / `123`** (`pstudent@vnu.edu.vn`) — *Private EV Student*: Đặt chỗ đỗ xe cá nhân theo ca, Check-in/out và đăng ký lịch sạc (`SUB-03`).
- **`operator` / `123`** (`operator@vnu.edu.vn`) — *Operator*: Giám sát mạng lưới, điều chuyển xe, quản lý sự cố, ưu tiên & lập lịch sạc, chạy đủ 5 kịch bản What-if (`SUB-04`, `SUB-05`, `SUB-06`).

## 3. Thứ tự demo 6 phân hệ

1. Đăng nhập `student`, vào **Khám phá**, lọc và đặt xe tại một Hub. Mở **Của tôi** để nhận xe bằng mã mô phỏng. Trả xe với pin 12% để tạo nhu cầu sạc xe dùng chung.
2. Đăng nhập `pstudent`, vào **Đỗ & Sạc**. Chọn ô có sạc và ca bao gồm giờ hiện tại nếu cần check-in ngay. Xác nhận phiếu, đăng ký sạc trong giờ đỗ và check-in qua **Phiếu đỗ & Lịch sạc của tôi**.
3. Đăng nhập `operator`, mở **Ưu tiên yêu cầu sạc**, chọn cùng Hub và bổ sung giờ cần xe cho yêu cầu xe dùng chung. Ngưỡng ưu tiên sạc là 30%. Ngưỡng vận hành của xe dùng chung là 20%. Xem phương án, xác nhận phần khả thi rồi đối chiếu công suất và trụ theo khung giờ. [Các bước demo SUB-04](modules/sub04/DEMO.md)
4. Mở **Tổng quan mạng lưới**, xem cảnh báo và tạo lệnh điều chuyển giữa hai Hub khả dụng. Sau đó dùng **Sự cố** để báo hỏng một trụ đã có lịch và xác nhận trụ thay thế ở **Lập lịch sạc**.
5. Mở **What-if Simulation**, chọn Hub và chạy từng kịch bản. Trong khi một phiên còn chạy, có thể mở Dashboard rồi quay lại để hủy phiên. Kết quả lưu trong sandbox.

Giữ cùng một tiến trình Streamlit khi đổi vai trò để các tuyến nghiệp vụ dùng chung dữ liệu. Khởi động lại tiến trình để phục hồi dữ liệu mẫu. Khóa xe, cảm biến bãi đỗ và thiết bị sạc được giả lập.

## 4. Chạy bộ kiểm thử tự động

Xem [kịch bản kiểm thử 6 SUB và cách gửi nhánh cho nhóm](TEST_PLAN.md).

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s modules/sub04 -p "test_*.py" -v
```
