# Demo SUB-04 · Smart Charging Management

Từ thư mục chứa `app.py`, cài các gói trong `requirements.txt` rồi chạy `python -m streamlit run app.py`. Dùng cùng một tiến trình ứng dụng cho các vai trò để chia sẻ dữ liệu demo.

## Chuẩn bị một yêu cầu Private EV

1. Chọn vai trò **Private EV Student**, mở **SUB-03 · Private EV Parking**.
2. Tại **Metro Station**, chọn một ô có sạc (ví dụ **PS-001** khi còn trống), giữ chỗ, nhập biển số rồi xác nhận. Chọn giờ rời đi cách hiện tại ít nhất 30 phút.
3. Check-in bằng phiếu vừa tạo. Gửi yêu cầu sạc với pin hiện tại 18%, mục tiêu 80% và giờ lấy xe nằm trong khung đỗ. Ghi lại mã yêu cầu.
4. Chuyển sang **Operator → SUB-04 · Smart Charging**, chọn cùng Hub.

## UC-08 · Theo dõi tài nguyên

Mở **Tài nguyên sạc**. Đối chiếu số trụ khả dụng với các dòng AVAILABLE, xem công suất từng trụ và giới hạn Hub. Sau khi xác nhận lịch ở UC-10, quay lại đây để thấy mã lịch trên trụ RESERVED.

## UC-09 · Ưu tiên yêu cầu

Mở **Hàng chờ ưu tiên** và tìm mã yêu cầu đã tạo ở SUB-03. Có thể lặp lại bước chuẩn bị với một ô đỗ có sạc khác, dùng mức pin 30%. Yêu cầu 18% đứng trước yêu cầu 30%. Khi pin bằng nhau, so giờ cần xe rồi đến thời điểm gửi. Bảng hiển thị lý do cho yêu cầu chưa thể xếp lịch. Yêu cầu thiếu dữ liệu nằm ở bảng riêng.

Ảnh minh họa có thêm hai yêu cầu xe dùng chung tạo qua hàm tích hợp SUB-02 của SUB-04. Một xe chưa có giờ cần sử dụng nên nằm ngoài bảng xếp hạng. Bộ dữ liệu khởi động mặc định có hàng chờ trống.

## UC-10 · Lập lịch và giải phóng trụ

1. Chọn mã yêu cầu trong hàng chờ, bấm **Đề xuất lịch**. Trong **Lịch sạc**, kiểm tra trụ, khung giờ và công suất. Lịch PROPOSED chưa giữ trụ.
2. Bấm **Xác nhận lịch** trước giờ bắt đầu. Kiểm tra lịch CONFIRMED và trụ RESERVED. Nếu khung giờ đã qua, quay lại hàng chờ và bấm **Đề xuất lịch** để tính lại.
3. Để demo hủy, bấm **Hủy lịch và yêu cầu** trước giờ bắt đầu hoặc dùng **Hủy yêu cầu sạc** ở SUB-03. Kiểm tra trạng thái CANCELLED và trụ được giải phóng nếu không còn lịch khác.
4. Để demo hoàn tất, dùng một yêu cầu mới. Sau giờ bắt đầu, nhập 40% rồi bấm **Cập nhật phiên sạc**. Trụ chuyển IN_USE. Cập nhật lên 100%, kiểm tra lịch COMPLETED và trạng thái trụ sau khi giải phóng. Xe cá nhân cần check-in trước khi bắt đầu sạc.

## Quy ước tích hợp

- SUB-03 tạo bản ghi Private EV và gửi mã yêu cầu. SUB-04 đọc lại chính bản ghi đó. Hai module dùng chung trạng thái yêu cầu PENDING, CONFIRMED và CANCELLED. Tiến độ và kết quả COMPLETED của phiên nằm trên lịch sạc.
- SUB-02 có thể gọi `receive_shared_vehicle_charging_need(state, vehicle_id, battery_level)` khi trả xe pin thấp. Operator bổ sung giờ cần xe trước khi xếp hạng.
- Giới hạn công suất lấy từ `charging_capacity_kw` của Hub. Nếu bộ dữ liệu chưa khai báo, dùng tổng công suất danh định của các trụ. Trụ IN_USE trong dữ liệu mẫu được tính tải theo công suất danh định.
- Với yêu cầu chỉ có giờ cần xe, đề xuất mặc định bắt đầu ở phút kế tiếp hoặc giờ bắt đầu đỗ nếu muộn hơn, kết thúc trước hoặc đúng giới hạn lấy xe và kết thúc đỗ.

Chạy kiểm thử từ thư mục chứa `app.py` bằng `python -m unittest modules.sub04.test_service -v`.

## Điểm cần phối hợp trước khi tích hợp cả nhóm

- Bản starter của SUB-02 còn thiếu thao tác trả xe. M2 cần gọi hàm nhận nhu cầu sạc sau khi trả xe pin thấp để demo từ màn hình Student.
- Trong SUB-03, thao tác hủy riêng yêu cầu sạc có kiểm tra kết quả SUB-04 trả về. Riêng thao tác hủy cả phiếu đỗ hiện bỏ qua kết quả này. Nếu lịch đã tới giờ bắt đầu nhưng xe chưa check-in, SUB-04 từ chối hủy lịch, còn SUB-03 vẫn hủy phiếu và yêu cầu. M3 cần kiểm tra kết quả trước khi ghi các trạng thái hủy. Có thể tái hiện bằng cách giữ phiếu đỗ RESERVED, xác nhận lịch, chờ tới giờ bắt đầu và hủy cả phiếu đỗ.

## Ảnh màn hình từ ứng dụng

- [UC-08 · Tài nguyên sạc tại Metro Station](demo/UC08.png)
- [UC-09 · Hàng chờ ưu tiên và yêu cầu thiếu dữ liệu](demo/UC09.png)
- [UC-10 · Lịch đã được Operator xác nhận](demo/UC10.png)
