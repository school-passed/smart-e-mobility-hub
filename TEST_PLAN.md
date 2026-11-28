# Kịch bản kiểm thử bản tích hợp 6 SUB

Phạm vi là bản Streamlit tích hợp, gồm Student UI và Operator UI theo bản cập nhật `5c845d7`. Các ca dùng dữ liệu mẫu trong một tiến trình. Kết quả thực tế có thể khác về mã hoặc số lượng khi đã có người thao tác trước.

## Chuẩn bị

Mở PowerShell tại thư mục chứa `app.py`. Tạo môi trường nếu máy chưa có `.venv`.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Chạy ứng dụng bằng lệnh sau. Mở [ứng dụng cục bộ](http://127.0.0.1:8501).

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

- Dùng mật khẩu `123` cho cả `student`, `pstudent` và `operator`. Mở mỗi vai trò ở một tab trên cùng URL.
- Khởi động lại Streamlit trước khi chạy kịch bản từ đầu để lấy lại dữ liệu mẫu. Refresh trình duyệt chỉ tải lại giao diện.
- Ghi các mã phiếu, xe, yêu cầu, lịch sạc, trụ và lệnh theo giá trị thực tế. Chọn **Metro Station (HUB-01)** cho xe dùng chung và đổi trụ. Chọn **HCMUT Campus (HUB-03)** cho xe cá nhân. Hai Hub dùng tên tiếng Việt tương ứng trong UI Student.
- Check-in và bắt đầu sạc dựa trên giờ máy chạy server. Chọn ca bao gồm giờ hiện tại nếu cần kiểm tra check-in. Các ca đến mốc hết hạn hoặc đang sạc có kiểm thử tự động với đồng hồ cố định.

## Kiểm thử tự động

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest modules.sub04.test_service -v
```

Bộ AppTest đi qua đăng nhập, điều hướng, nhận và trả xe, đỗ và sạc cá nhân, xác nhận và đổi trụ, tạm ẩn và hiện lại yêu cầu, mở lịch hẹn, ngắt phiên sạc và What-if. Bộ service kiểm tra các trường hợp phân bổ đồng thời, thiếu dữ liệu, phiếu hết hạn, lỗi tài nguyên và cô lập sandbox.

## Kiểm thử thủ công

Chạy theo thứ tự dưới đây hoặc dùng lượt dữ liệu mới cho từng cụm ca.

| Mã | Người dùng và thao tác | Kết quả mong đợi |
|---|---|---|
| UI-01 | Student đăng nhập, cuộn **Khám phá**, chuyển qua **Của tôi**, **Đỗ & Sạc** và **Hồ sơ**. | Thanh 4 tab vẫn nằm trong vùng nhìn thấy khi cuộn. Trang tương ứng tải được. |
| UI-02 | Operator đăng nhập rồi mở lần lượt 7 mục sidebar. Từ **Tổng quan mạng lưới**, mở một Hub, quay lại và bấm **Chạy What-if →**. | Sidebar chọn đúng mục. Tiêu đề, bộ chọn Hub, thẻ chỉ số và bảng hiển thị đọc được. Nút tắt chuyển đúng màn. |
| E2E-01 · SUB-01 | Student lọc Hub còn xe, mở Metro và đặt xe. Đọc mã lấy xe. Nếu kiểm tra hủy phiếu, hủy rồi đặt lại để tiếp tục. | Phiếu `PENDING`, có mã lấy xe. Hủy giải phóng lượt đặt. |
| E2E-02 · SUB-02 | Ở Metro, nhập mã sai thử một lần. Báo lỗi chiếc xe đang chọn, chọn xe khác, nhập mã đúng và xác nhận. Trả xe về Metro với pin **12%**. | Mã sai giữ phiếu. Xe lỗi bị cô lập mà phiếu vẫn dùng được. Nhận xe đóng phiếu đặt. Trả xe đóng chuyến, ghi ô trả và sinh yêu cầu sạc xe dùng chung. |
| E2E-03 · SUB-03 | `pstudent` đặt ô có sạc tại HCMUT Campus, ví dụ **P-41** nếu còn trống. Chọn ca, gửi yêu cầu từ **30% lên 85%** và mở **Phiếu đỗ & Lịch sạc của tôi**. Check-in khi đang trong ca. | Có phiếu và yêu cầu `PENDING` liên kết cùng Hub. Check-in hợp lệ chuyển phiếu sang `IN_USE`. Check-in ngoài ca bị từ chối. |
| E2E-04 · SUB-04 | Operator mở **Ưu tiên yêu cầu sạc** tại Metro. Bấm **Tạm ẩn** trên yêu cầu thiếu giờ cần xe, rồi **Hiện lại … yêu cầu đã tạm ẩn**. Sau đó chọn yêu cầu và **Lưu giờ cần xe** với một giờ trong tương lai. | Tạm ẩn chỉ đổi cách hiển thị trong phiên. Hiện lại khôi phục dòng. Bổ sung giờ đưa xe 12% vào nhóm dưới 30%. |
| E2E-05 · SUB-04 | Mở **Lập lịch sạc** → **Lập phương án theo thứ tự ưu tiên** → **Lập tất cả đề xuất** → **Xác nhận phần khả thi**. Mở **Giám sát tài nguyên sạc**, chọn khoảng giờ giao với lịch, sau đó **Xem lịch hẹn**. | Phương án giữ chỗ sau xác nhận. Trụ và đỉnh công suất xuất hiện trong khung giờ. **Xem lịch hẹn** đưa đến danh sách lịch đã xác nhận tại cùng Hub. |
| E2E-06 · SUB-04/05 | Trước khi phiên bắt đầu, Operator báo sự cố cho đúng trụ đã được phân bổ ở Metro. Từ hồ sơ sự cố mở **Lập lịch sạc**, bấm **Tìm trụ thay thế** rồi xác nhận. | Trụ cũ bị cô lập. Lịch giữ mã đến khi xác nhận phương án. Trụ được đổi nếu còn đáp ứng giờ và công suất. |
| E2E-07 · SUB-04 | Trên ca riêng, chờ đến giờ bắt đầu của một lịch xe dùng chung. Cập nhật tiến độ lên **40%**. Ở màn **Giám sát tài nguyên sạc**, mở **Ngắt an toàn** rồi **Xác nhận ngắt**. | Phiên đi vào lịch sử ở trạng thái **Đã ngắt**, vẫn ghi tiến độ 40%. Xe pin thấp vẫn chờ sạc và có yêu cầu tiếp theo. |
| E2E-08 · SUB-05 | Ở **Điều chuyển xe**, chọn **Dormitory Zone → HCMUT Campus**, nhập 1 xe khả dụng và xác nhận. Kiểm tra thông tin chỗ đích rồi bấm **Hoàn tất**. Ở **Sự cố**, thử bật tắt **Hiện cả sự cố đã giải quyết** sau khi giải quyết một mục. | Lệnh chuyển từ đang điều chuyển sang hoàn tất. Chỗ đích đã giữ được phản ánh trong số có thể tiếp nhận. Bộ lọc sự cố hiện đúng danh sách. |
| E2E-09 · SUB-06 | Chạy **Peak student arrivals** ở Metro với nền 6 và tăng 100%. Thử **Full parking**, **Charging surge**, **Charging-point failures** và **Vehicle concentration**. So sánh Dashboard trước và sau. | Có kết quả trước/sau và khuyến nghị phù hợp. Dữ liệu vận hành giữ nguyên. Hủy phiên khi phép tính còn chạy thì kết quả phiên đó không xuất hiện. |

### Các ca biên để nhóm đối chiếu

- **Công suất và tranh chấp.** Hai yêu cầu trùng giờ chỉ được xác nhận khi còn cổng phù hợp và tổng kW trong giới hạn. Nếu một dòng đổi trạng thái sau khi xem phương án, xác nhận lại phải báo lỗi và giữ phần còn lại nguyên vẹn.
- **Thời gian.** Thu hồi lịch đã qua giờ kết thúc mà chưa bắt đầu, xử lý phiếu đỗ chưa check-in và chặn việc hủy phiên đang sạc qua luồng hủy lịch thông thường.
- **Mất kết nối.** Mở cùng lúc hai phiên Operator. Một phiên báo sự cố, phiên kia xem trạng thái tự cập nhật. Với Hub đích mất kết nối, thử tạo hoặc hoàn tất điều chuyển và đọc lý do từ chối.
- **Kích thước màn hình.** Kiểm tra Student ở chiều rộng khoảng 440 px và Operator ở 1440 px. Kiểm tra thêm ở 1024 px nếu nhóm dùng máy chiếu hoặc laptop hẹp.

Ghi mỗi kết quả theo dạng **mã ca · giờ thử · dữ liệu dùng · kết quả thực tế · đạt/chưa đạt · ảnh hoặc bước tái hiện**. Các phép đo đáp ứng cần ghi điều kiện và số phiên đồng thời.

## Gửi nhánh cho nhóm bằng Git

Tại repo tích hợp, xác nhận đang ở `integration/submission-review`. Sau đó kiểm tra các file đã stage rồi mới commit và push.

```powershell
git branch --show-current
git status --short
git add -- app.py README.md PROJECT_TASKS.md TEST_PLAN.md modules shared tests .streamlit/config.toml
git diff --cached --check
git diff --cached --stat
git commit -m "Integrate updated Operator UI and validate MVP workflows"
git push -u origin integration/submission-review
```

Nếu GitHub yêu cầu xác thực lại, dùng `git credential-manager github login --browser --force`, hoàn tất trên trình duyệt rồi chạy lại lệnh push. Sau khi push, mở [Pull Request từ nhánh tích hợp vào main](https://github.com/school-passed/smart-e-mobility-hub/compare/main...integration/submission-review?expand=1). Ghi các ca đã chạy và đính kèm ảnh những màn Operator đã chỉnh.

Thành viên đã clone có thể lấy nhánh bằng `git fetch origin` rồi chạy `git switch --track origin/integration/submission-review` ở lần đầu. Nếu máy đã có nhánh theo dõi, dùng `git switch integration/submission-review` và `git pull --ff-only`.
