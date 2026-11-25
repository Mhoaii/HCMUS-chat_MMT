# Hướng dẫn sử dụng LAN Chat

Ứng dụng giúp các máy trong cùng mạng LAN/Wi-Fi tìm thấy nhau, trò chuyện
và gửi file. Bạn có thể dùng giao diện cửa sổ hoặc terminal.

## 1. Chuẩn bị và cài đặt

- Cài Python 3.10 trở lên. Trên Windows, chọn thành phần Tcl/Tk khi cài Python.
- Các máy dùng cùng phiên bản mã nguồn, kết nối cùng LAN/Wi-Fi.
- Mỗi người dùng một username khác nhau, ví dụ `hoang`, `hoai`, `minh`.
- Khi Windows hỏi quyền truy cập mạng, cho phép Python trên mạng nội bộ đang dùng.

Nếu đã có Git, lấy mã nguồn bằng lệnh sau.

```powershell
git clone --branch Hoang https://github.com/Mhoaii/HCMUS-chat_MMT.git
cd HCMUS-chat_MMT
py -m pip install -r requirements.txt
```

Nếu tải mã nguồn dưới dạng ZIP, giải nén rồi mở terminal tại thư mục chứa
`main.py` và chạy lệnh cài dependency ở trên.

Các lệnh trong hướng dẫn được chạy từ thư mục gốc dự án. Nếu máy dùng lệnh
`python` để mở Python, có thể thay `py` bằng `python`.

## 2. Dùng giao diện cửa sổ

### Mở ứng dụng và nhập hồ sơ

```powershell
py -B -m ui.app
```

1. Nhập **Username**. Đây là tên định danh dùng khi tìm người và gửi lời mời.
2. Nhập **Tên hiển thị** và **Chức danh** nếu muốn.
3. Bấm **Bắt đầu kết nối** hoặc nhấn Enter trong ô nhập.
4. Mở ứng dụng trên máy còn lại với username khác.

Ứng dụng tự chọn cổng TCP trống và quảng bá thông tin qua UDP. Nếu bỏ trống
tên hiển thị, ứng dụng dùng username. Chức danh mặc định là `Nhân viên`.

### Tìm người và đổi trạng thái

- Danh sách **Người dùng LAN** hiển thị những người đã được phát hiện.
- Bấm **↻** cạnh tiêu đề danh sách để làm mới nội dung đang hiển thị.
- Chọn `online` hoặc `away` ở góc trên bên phải để đổi trạng thái.
- Bật hoặc tắt **Hiện thông báo** để điều chỉnh thông báo thay đổi danh sách người dùng.

Presence được gửi mỗi 3 giây. Khi một người ngừng phát presence, ứng dụng
loại họ khỏi danh sách sau khoảng 10 giây. Trạng thái `away` vẫn cho phép
người dùng nhận lời mời và trò chuyện.

### Mời chat và gửi tin nhắn

1. Chọn người nhận trong **Người dùng LAN**.
2. Bấm **Mời trò chuyện**.
3. Phía nhận chọn lời mời trong danh sách hội thoại rồi bấm **Đồng ý** hoặc **Từ chối**.
4. Khi phiên chat được đồng ý, ô soạn tin và nút gửi được bật.
5. Nhập nội dung, nhấn Enter hoặc bấm **Gửi**.

Chọn một mục trong **Cuộc trò chuyện** để chuyển hội thoại. Tin đến từ
người đang ở hội thoại khác được lưu và hiển thị số chưa đọc. Nội dung đang
soạn được giữ riêng cho từng người khi chuyển qua lại.

Nhãn **Đã nhận** xác nhận ứng dụng phía nhận đã tiếp nhận tin nhắn.

### Gửi và nhận file

Phía gửi thực hiện các bước sau trong phiên chat đã được đồng ý.

1. Bấm **Chọn file** và chọn file trên máy.
2. Kiểm tra tên file xuất hiện dưới ô soạn tin.
3. Nếu chọn nhầm, bấm **Bỏ chọn** rồi chọn lại.
4. Bấm **Gửi file** để gửi lời mời nhận file.

Phía nhận chọn cuộc chat với người gửi, rồi bấm **Nhận file** hoặc
**Từ chối file** trên thẻ lời mời. Dữ liệu được truyền sau khi người nhận đồng ý.

Tiến độ hiển thị trong lịch sử hội thoại. Khi nhận thành công, phía nhận
thấy thông báo `100% · Đã lưu tại ...`. Bạn vẫn có thể nhắn tin trong lúc truyền.

### Rời chat và thoát ứng dụng

- Gõ `/leave` trong cuộc chat đang hoạt động rồi nhấn Enter để đóng phiên đó.
- Dùng menu **Ứng dụng → Thoát**, nhấn **Ctrl+Q** hoặc đóng cửa sổ để thoát.
- Gõ `/quit` trong ô soạn tin đang được bật rồi gửi cũng sẽ thoát ứng dụng.

## 3. Dùng terminal

```powershell
py -B main.py
```

Nhập username, tên hiển thị và chức danh khi chương trình hỏi. Chờ vài giây
để discovery nhận thông tin người dùng khác, sau đó dùng các lệnh bên dưới.

| Lệnh | Cách dùng |
|---|---|
| `/list` | Xem số thứ tự, username, tên hiển thị, IP, cổng TCP và trạng thái |
| `/chat hoai` | Mời chat với `hoai`, hoặc chuyển về phiên đang mở |
| `/chat 1` | Chọn người số 1 trong lần `/list` gần nhất |
| `/chat @123` | Chọn username `123`; dùng `/chat @@hoai` cho username `@hoai` |
| `/chats` | Xem các hội thoại, trạng thái phiên và số tin chưa đọc |
| `/accept hoang` | Đồng ý lời mời chat từ `hoang` |
| `/accept` | Đồng ý lời mời đầu tiên đang chờ; nếu chưa có sẽ thông báo |
| `/decline hoang` | Từ chối lời mời chat từ `hoang` |
| `/send "C:\Tai lieu\bao_cao.pdf"` | Gửi lời mời file cho người trong cuộc chat hiện tại |
| `/acceptfile <mã>` | Đồng ý lời mời file có mã được in trong terminal |
| `/declinefile <mã>` | Từ chối lời mời file có mã được in trong terminal |
| `/status online` | Đổi trạng thái thành online |
| `/status away` | Đổi trạng thái thành away |
| `/leave` | Đóng cuộc chat hiện tại và trở về prompt chính |
| `/help` | Xem hướng dẫn các lệnh |
| `/quit` | Thoát chương trình và dọn các dịch vụ mạng |

Nhập văn bản rồi Enter để gửi tin sau khi người nhận đồng ý chat. Nội dung
bắt đầu bằng `/` được xử lý như lệnh. Nếu đường dẫn file có khoảng trắng,
đặt đường dẫn trong dấu ngoặc kép như ví dụ trong bảng.

Để nhận file, trước tiên chọn đúng cuộc chat với người gửi bằng `/chat username`.
Sau đó thay `<mã>` bằng mã thật trong lời mời, ví dụ
`/acceptfile 0123456789abcdef0123456789abcdef`.

Khi đang chat với A mà B gửi tin, terminal thông báo số tin chưa đọc từ B.
Dùng `/chat B` với username thực tế để chuyển sang B và hiển thị lịch sử.
`/chats` giúp tìm lại các hội thoại. Dòng đang gõ được giữ khi có thông báo mạng.

## 4. File được lưu ở đâu?

File nhận được lưu trong thư mục `downloads/` thuộc **thư mục chạy ứng dụng**.
Ví dụ, nếu mở ứng dụng từ `D:\git\HCMUS-chat_MMT`, file nằm tại
`D:\git\HCMUS-chat_MMT\downloads`.

- Thư mục được tạo khi bắt đầu nhận dữ liệu file.
- File nằm trên máy nhận. Hãy xem đường dẫn trong thông báo nhận thành công.
- Khi trùng tên, ứng dụng thêm số vào tên file để giữ các file đã có.
- Giới hạn hiện tại là **100 MiB/file**.
- Ứng dụng kiểm tra SHA-256 trước khi công bố file hoàn chỉnh và dọn file tạm khi truyền lỗi.

Bạn có thể mở thư mục bằng File Explorer, hoặc chạy lệnh sau từ thư mục dự án.

```powershell
explorer .\downloads
```

## 5. Xử lý sự cố thường gặp

| Hiện tượng | Cách kiểm tra và xử lý |
|---|---|
| Danh sách người dùng trống | Kiểm tra cùng LAN/Wi-Fi, username khác nhau và quyền firewall của Python. Chờ vài giây rồi tải lại danh sách |
| Đã thấy người nhưng chưa gửi tin được | Gửi lời mời chat và đợi phía nhận đồng ý. Xem thông báo trạng thái phiên |
| Nút Chọn file hoặc Gửi bị mờ | Chọn cuộc chat đã được đồng ý và còn kết nối |
| File đang chờ người nhận | Phía nhận mở đúng hội thoại và bấm Nhận file, hoặc dùng `/acceptfile` với đúng mã |
| Chưa thấy thư mục downloads | Kiểm tra trên máy nhận, xác nhận đã đồng ý nhận file và xem đường dẫn khi hoàn tất |
| File không tồn tại hoặc quá lớn | Chọn lại file còn tồn tại, dung lượng tối đa 100 MiB |
| Truyền file bị lỗi hoặc mất kết nối | Đọc thông báo lỗi, thiết lập lại phiên chat nếu cần rồi gửi lại file từ đầu |
| Peer biến mất khỏi danh sách | Kiểm tra ứng dụng phía kia còn chạy và kết nối mạng còn hoạt động |
| Báo thiếu prompt_toolkit | Chạy `py -m pip install -r requirements.txt` bằng cùng Python dùng mở ứng dụng |
| Báo lỗi Tkinter | Kiểm tra bằng `py -m tkinter`; bổ sung thành phần Tcl/Tk trong bộ cài Python |

## 6. Kiểm tra nhanh trước khi sử dụng hoặc demo

1. Mở hai peer với username khác nhau và xác nhận thấy nhau trong danh sách.
2. Đổi trạng thái một peer, kiểm tra phía kia cập nhật.
3. Gửi lời mời, đồng ý rồi chat hai chiều.
4. Gửi một file nhỏ, đồng ý nhận và mở file trong `downloads` trên máy nhận.
5. Gửi file lớn hơn để quan sát tiến độ, đồng thời tiếp tục nhắn tin.
6. Thêm peer thứ ba để kiểm tra tin chưa đọc và chuyển hội thoại.
7. Rời chat, gửi lời mời lại và kiểm tra thoát ứng dụng.

Để chạy bộ kiểm thử tự động từ thư mục dự án, dùng lệnh sau.

```powershell
py -X utf8 -B -m unittest discover -s tests -v
```

Test giao diện cần môi trường có màn hình và Tkinter. Lịch sử, tin chưa đọc
và nội dung đang soạn được lưu trong RAM của lần chạy hiện tại. File đã nhận
thành công vẫn nằm trên ổ đĩa khi đóng ứng dụng.
