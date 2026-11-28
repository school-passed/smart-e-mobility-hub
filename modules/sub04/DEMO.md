# Demo SUB-04 · Quản lý sạc

Chạy ứng dụng theo [README](../../README.md). Các vai trò dùng chung một tiến trình Streamlit.

## Chuẩn bị yêu cầu

- Với xe dùng chung, trả xe có pin dưới 20% bằng tài khoản `student`. Sau đó dùng tài khoản `operator` bổ sung giờ cần xe trong màn **Ưu tiên yêu cầu sạc**.
- Với xe cá nhân, dùng tài khoản `pstudent` đăng ký ô có hỗ trợ sạc ở **Đỗ & Sạc**. Đặt giờ sạc nằm trong giờ đỗ, rồi check-in khi ca bắt đầu. Ghi lại mã yêu cầu và tên Hub.

## UC-08 · Công suất và tài nguyên

Mở **Giám sát tài nguyên sạc**, chọn Hub và mở **Công suất và khả dụng theo khung giờ**. Chọn ngày, giờ bắt đầu và giờ kết thúc. So sánh giới hạn của Hub, công suất đang dùng và đỉnh công suất đã phân bổ. Mỗi dòng cho biết trụ, mã lịch trong khung giờ và độ tin cậy dữ liệu.

## UC-09 · Xếp hạng

Mở **Ưu tiên yêu cầu sạc**. Nhóm pin dưới 30% đứng trước nhóm từ 30% trở lên. Trong cùng nhóm, xét giờ dùng dự kiến đã biết trước, sau đó dùng thời điểm gửi để xử lý trường hợp đồng hạng. Yêu cầu thiếu dữ liệu cần thiết có lý do ở nhóm chờ xác minh.

## UC-10 · Lập lịch, đổi trụ và hoàn tất

1. Trong **Lập lịch sạc**, mở **Lập phương án theo thứ tự ưu tiên** rồi bấm **Lập tất cả đề xuất**. Xem các dòng có thể phân bổ và lý do các yêu cầu còn chờ. Bấm **Xác nhận phần khả thi** để giữ trụ và công suất. Có thể thao tác từng yêu cầu bằng **Tạo đề xuất** và **Xác nhận**.
2. Để demo đổi trụ, mở **Sự cố**, báo hỏng trụ đã được xác nhận rồi theo lối tắt **Lập lịch sạc**. Chọn **Tìm trụ thay thế** và xác nhận phương án mới. Mã lịch được giữ khi chuyển trụ.
3. Để demo hủy, ở **Giám sát tài nguyên sạc**, bấm **Xem lịch hẹn**, rồi chọn **Hủy lịch** trước giờ bắt đầu. Nếu là xe dùng chung, nhu cầu sạc xuất hiện lại trong hàng chờ với mã mới. Lịch đã quá giờ kết thúc mà chưa bắt đầu sẽ hết hạn và nhả phân bổ.
4. Để demo phiên thành công, cập nhật tiến độ sau khi đến giờ bắt đầu. Xe cá nhân cần check-in trước. Cập nhật lên 100% để hoàn tất và giải phóng trụ. Với xe dùng chung, ứng dụng demo áp dụng mức pin mục tiêu 100%.
5. Để demo ngắt khẩn cấp, báo sự cố mức cao trên trụ đang sạc, rồi dùng **Dừng khẩn cấp phiên**. Phiên giữ tiến độ cuối, trụ được cô lập và xe dùng chung được đưa lại vào hàng chờ.

Các ảnh cũ trong thư mục `demo/` thuộc giao diện trước khi hợp nhất Student UI và Operator UI.
