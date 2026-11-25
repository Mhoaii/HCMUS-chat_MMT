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
6. Gõ `/quit` rồi bấm **Gửi** hoặc Enter để rời cuộc chat đang mở.
   Hai đầu đóng kết nối đó; cửa sổ, discovery, lịch sử và các cuộc chat khác
   vẫn được giữ. Muốn trò chuyện lại thì gửi lời mời mới.

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

Mỗi dòng TCP là một JSON UTF-8, được gửi bằng hàm `send_message` hiện có.
Trường chung: `protocol="lan-chat-ui/1"`, `request_id`, `type`.

| type | Trường bổ sung | Ý nghĩa |
| --- | --- | --- |
| request | username, display_name, tcp_port, to | Mời đúng người nhận |
| accept | username | Đồng ý lời mời |
| decline | Không có | Từ chối rồi đóng socket |
| message | text | Văn bản sau khi được đồng ý |

`request_id` là UUID hex, dùng để phân biệt phiên và loại sự kiện của socket cũ.
Username người gửi được lấy từ lời mời, không đoán bằng IP hoặc cổng nguồn TCP.
Đây là danh tính tự khai trong LAN, chưa phải đăng nhập/xác thực.
Tên và cổng trong lời mời không thay thế trạng thái presence UDP.

JSON giúp nội dung như `ACCEPT`, dấu ngoặc hay newline được truyền đúng dạng
tin nhắn. Tin nhắn tối đa 16.000 byte UTF-8. Các gói được gửi tuần tự bởi một
writer; mỗi socket có đúng một reader.

Hai UI phải cùng dùng giao thức này. Console cũ vẫn chạy riêng nhưng không
thực hiện lời mời với UI. Hiện vẫn dùng framing newline; header type + length
theo yêu cầu đồ án là phần cần thống nhất tiếp với người phụ trách TCP.
Sự kiện `sent` chỉ xác nhận `sendall` hoàn tất, chưa có ACK từ ứng dụng nhận.
Lịch sử nằm trong RAM. Nút Chọn file còn khóa, chưa có truyền file.

## Kiểm thử

```powershell
python -X utf8 -B -m unittest discover -s tests -p test_chat_session.py -v
```

Test sử dụng socket thật trên loopback; các test UI tạo widget Tk thật nhưng
ẩn cửa sổ. Chúng không thay thế kiểm thử hai máy LAN và thao tác trực tiếp.
