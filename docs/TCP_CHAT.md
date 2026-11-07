# TCP chat đã tích hợp

Tham khảo `tcp_chat.py` tại https://github.com/Mhoaii/HCMUS-chat_MMT,
commit `2c711c8e7e58f8dee7a3896d529e0ed5f6de5382`.
Bản gốc có accept/connect, sendall và thread nhận độc lập, một server/một client,
phân tách tin bằng newline. Bản tích hợp sử dụng cùng mô hình socket/thread,
được viết lại thành các lớp để kết nối UDP discovery và GUI hiện có.
**Hai bản không tương thích wire protocol**, không chạy một đầu bằng script gốc.

## Chạy

Từ thư mục dự án, hai terminal có username và TCP port khác nhau:

```powershell
python main.py --username nnah --name nnah --job nnah --port 5001
python main.py --username oithoinao --name oithoinao --job oithoinao --port 6000
```

Chờ 3–4 giây, gõ `/list`, rồi `/chat oithoinao` trên terminal thứ nhất.
Nhập tin bình thường để gửi; bên kia dùng `/chat nnah` để trả lời.
`/msg username nội_dung` gửi nhanh không cần đổi người đang chat.
`/online`, `/away` đổi trạng thái; `/leave` bỏ lựa chọn chat; `/quit` đóng backend.
Nhận tin ở console có thể xen dòng đang nhập; nên dùng GUI để có vùng soạn riêng.

```powershell
python main.py --gui
# Hoặc:
python -m ui
# Giao diện mẫu cũ, không dùng mạng:
python -m ui --demo
```

Trên hai máy thật: cùng LAN, cho phép ứng dụng Python qua Windows Firewall
trên mạng riêng; UDP dùng chung 1717, TCP dùng cổng nhập trong hồ sơ.
Một máy chạy nhiều instance phải có username/cổng TCP riêng.
UDPListener bật SO_REUSEADDR trước bind để các instance chia sẻ cổng discovery.
Broadcast phụ thuộc card mạng/router; VPN hoặc Wi-Fi client isolation có thể cản discovery.

## Luồng và trách nhiệm lớp

```text
Console / ChatUI
      | send_message(username, text, message_id)
 ChatManager ---- DiscoveryService.get_peer() --> IP + TCP port
      |
 ConnectionManager --> worker --> TCPClient.exchange()
                                     |
                  TCP [4-byte length][JSON UTF-8]
                                     |
                    TCPServer của người nhận
                    kiểm tra CHAT + recipient
                    callback --> hàng đợi UI
                                     |
                          ACK cùng message_id
                                     |
                    sender nhận ACK --> cập nhật UI
```

Mỗi máy mở TCP server trước khi quảng bá UDP. Server nhận đồng thời tối đa 32
kết nối, bộ gửi tối đa 16 worker. Mỗi tin mở một kết nối, gửi CHAT, nhận ACK rồi
đóng; nhiều cuộc chat không dùng chung socket. Cách này đơn giản để tích hợp,
đổi lại có chi phí handshake mỗi tin; chưa có kết nối dài hạn.
Các lớp sử dụng composition, không có quan hệ cha/con tự tạo.

`protocol.py`: đọc đủ byte bằng `recv_exact`, validate và encode/decode frame.
`tcp_server.py`: listen/accept, worker nhận và gửi ACK sau callback thành công.
`tcp_client.py`: connect/sendall/nhận ACK, kiểm tra ID và hai định danh.
`connection_manager.py`: tác vụ gửi nền, timeout và đóng socket.
`chat_manager.py`: ghép các thành phần, snapshot peer cho UI, chống lặp trong RAM.

Ví dụ payload (header 4 byte là số BYTE của JSON UTF-8, không tính chính header):

```json
{"type":"CHAT","sender":"nnah","recipient":"oithoinao","message_id":"id-1","text":"Chào bạn\nDòng hai"}
{"type":"ACK","sender":"oithoinao","recipient":"nnah","message_id":"id-1"}
```

Giới hạn frame 1 MiB, timeout socket 5 giây. Tin Unicode/nhiều dòng không bị
tách sai. ACK là ứng dụng nhận đã tiếp nhận sự kiện, chưa phải đã xem hay
đã ghi SQLite. Mất ACK có thể xảy ra sau khi bên kia đã nhận tin: sender báo
chưa có ACK, không tự kết luận bên kia chưa nhận. Không tự gửi lại.
Chống trùng giữ 4096 cặp (sender, message_id) gần nhất trong RAM, mất khi khởi động lại.

Phạm vi hiện tại: chat text P2P online. Chưa có offline relay, đăng nhập bảo mật,
TLS, lưu lịch sử bền vững, seen hay truyền file. username/ACK chưa có xác thực
mật mã; kiểm tra ID và endpoint không ngăn được một peer LAN giả danh.
Nút file trong GUI báo rõ chưa hỗ trợ, không mô phỏng truyền thành công.

## Kiểm thử

```powershell
python -B -m unittest discover -s tests -v
```

Kiểm thử tự động TCP dùng loopback, cổng tạm hệ điều hành và socket thật.
Vẫn cần demo hai máy LAN để xác nhận firewall/broadcast trong môi trường thực.
