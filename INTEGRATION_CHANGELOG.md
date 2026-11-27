# Change log tích hợp đề xuất (không phải báo cáo đã nghiệm thu)

| Mã | File | Trước | Sau | Lý do |
|---|---|---|---|---|
| INT-01 | app.py | Menu SUB-01 đến SUB-06 | Menu chức năng theo role | Một sản phẩm thay vì sáu demo riêng |
| INT-02 | shared/state.py | `temporary_holds`/`shared_charging_requests` tạo động | Khai báo nhất quán ở seed | Schema chung minh bạch |
| INT-03 | sub02/service.py | Low-battery request `CRQ-` dùng `battery_level` trong private list | Gọi SUB-04 service, lưu `SHRQ-` với `current_battery` | Sửa contract SUB-02→04 |
| INT-04 | sub02/service.py | Code rỗng được coi như không cần kiểm tra | Bắt buộc code khớp | Phù hợp UC-04 |
| INT-05 | sub05/service.py | Gọi expire không có state, lỗi bị bỏ qua | Truyền `get_state()` | Đảm bảo reservation hết hạn khi mở dashboard |
| INT-06 | sub06/service.py | Chỉ đọc private charging_requests | Đếm cả shared_charging_requests | Simulation phản ánh thêm nhu cầu sạc xe dùng chung |
| INT-07 | shared/auth.py | Có thể tự tạo role Operator | Chỉ Student/Private EV Student đăng ký | Phù hợp quyền demo ban đầu |
| INT-08 | tests/ | Thiếu E2E service chung | Thêm 4 integration tests | Chặn regression khi ghép module |

Các bug chưa sửa được liệt kê ở `INTEGRATION_GUIDE.md`. Thay đổi giữ cấu trúc modular monolith, không chuyển framework hay thêm database.
