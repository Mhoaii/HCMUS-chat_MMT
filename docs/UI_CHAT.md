# Trò chuyện trong cửa sổ Tkinter

Chạy từ thư mục gốc dự án:

```powershell
python -B -m ui.app
```

1. Mở ứng dụng ở hai máy cùng LAN, chọn username khác nhau.
2. Chờ người kia xuất hiện trong User; `away` vẫn nhận được lời mời.
3. Chọn người đó, bấm **Mời trò chuyện** trong khung hội thoại.
4. Phía nhận chọn mục **Lời mời** trong Cuộc chat gần đây, rồi **Đồng ý**
   hoặc **Từ chối**. Lời mời không tự đổi hội thoại đang mở.
5. Khi đồng ý, hai bên nhập tin và bấm **Gửi** hoặc Enter.
6. Để gửi file, bấm **Chọn file** và xác nhận file trong hộp thoại. Bên nhận mở đúng hội thoại, xem tên và dung lượng trên khung lời mời rồi bấm **Đồng ý** hoặc **Từ chối**.
7. Khi nhận xong, lịch sử hiện `100% · Đã lưu tại ...`. File nằm trong `downloads/` của thư mục chạy ứng dụng trên máy nhận.

Không cần bật TCP hay bấm accept kỹ thuật. Listener và vòng accept tự chạy
khi bấm Bắt đầu. Một socket sau khi được đồng ý dùng cho cả hai chiều.
Lời mời chưa xử lý hết hạn sau 30 giây; có thể mời lại.
Hai bên cùng mời được coi là cùng đồng ý: giữ kết nối do username nhỏ hơn
theo thứ tự chuỗi khởi tạo, đóng kết nối thừa.

## Phân chia trách nhiệm

- `tcp_chat.py`: giữ nguyên các hàm connect, gửi/nhận UTF-8 kết thúc bằng newline
  và bản console của đồng đội.
- `tcp_service.py`: listener hiện có, bổ sung timeout tùy chọn cho accept.
- `chat_session.py`: service dành cho UI, quản lý lời mời, timeout,
  reader/writer riêng cho từng socket và thu hồi tài nguyên.
- `ui/app.py`: hiển thị trạng thái và thao tác người dùng. Worker gửi sự kiện
  qua queue; chỉ luồng Tk cập nhật widget, lịch sử, unread và nội dung đang gõ.

Socket chết được phát hiện qua EOF/lỗi TCP. Mất presence UDP không tự đóng
cuộc chat TCP còn hoạt động. Ô nhập có nội dung riêng theo từng hội thoại.
Tắt Hiện thông báo chỉ tắt thông báo presence, không giấu lời mời đang chờ.

## Hợp đồng dữ liệu giữa hai UI

Mỗi bản tin điều khiển gồm header 5 byte (1 byte loại, 4 byte độ dài theo thứ tự mạng) và payload JSON UTF-8. Trường `type` được khôi phục từ header khi đọc.
Trường chung: `protocol="lan-chat-ui/1"`, `request_id`, `type`.

| type | Trường bổ sung | Ý nghĩa |
| --- | --- | --- |
| request | username, display_name, tcp_port, to | Mời đúng người nhận |
| accept | username | Đồng ý lời mời |
| decline | Không có | Từ chối rồi đóng socket |
| message | text, message_id | Văn bản sau khi được đồng ý |
| ack | message_id | Ứng dụng đối phương đã tiếp nhận tin |
| file.offer | transfer_id, name, size, sha256 | Mời nhận file |
| file.reply | transfer_id, accepted | Trả lời lời mời |

`request_id` là UUID hex, dùng để phân biệt phiên và loại sự kiện của socket cũ.
Username người gửi được lấy từ lời mời, không đoán bằng IP hoặc cổng nguồn TCP.
Đây là danh tính tự khai trong LAN, chưa phải đăng nhập/xác thực.
Tên và cổng trong lời mời không thay thế trạng thái presence UDP.

JSON giúp nội dung như `ACCEPT`, dấu ngoặc hay newline được truyền đúng dạng
tin nhắn. Tin nhắn tối đa 16.000 byte UTF-8. Các gói được gửi tuần tự bởi một
writer; mỗi socket có đúng một reader.

UI và terminal dùng chung giao thức. Sau khi người nhận đồng ý, bên gửi mở socket dữ liệu riêng, gửi `file.open`, đúng số byte đã báo rồi gửi `file.end`. Bên nhận kiểm tra SHA-256, lưu file và trả `file.saved`. Lịch sử chat nằm trong RAM.

## Kiểm thử

```powershell
python -X utf8 -B -m unittest discover -s tests -p test_chat_session.py -v
```

Test sử dụng socket thật trên loopback; các test UI tạo widget Tk thật nhưng
ẩn cửa sổ. Chúng không thay thế kiểm thử hai máy LAN và thao tác trực tiếp.
