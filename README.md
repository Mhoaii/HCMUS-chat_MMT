# LAN Chat — UDP discovery và TCP chat

Đã nối chat text vào backend và giao diện. Hướng dẫn chi tiết: [TCP_CHAT.md](TCP_CHAT.md).

```powershell
python main.py --gui
# Hoặc console, mỗi instance dùng username và TCP port riêng:
python main.py --username nnah --name nnah --job Test --port 5001
python main.py --username oithoinao --name oithoinao --job Test --port 6000
```

Console: chờ discovery, `/list`, `/chat username`, nhập tin để gửi, `/quit` để thoát.
Chạy `python -m ui --demo` nếu chỉ muốn xem UI mẫu không có mạng.
Chat hiện cần hai peer cùng chạy; ACK là ứng dụng bên kia đã nhận, chưa phải đã xem.
Truyền file thật và lưu lịch sử xuống đĩa chưa được triển khai.

Kiểm thử: `python -B -m unittest discover -s tests -v`.

## Cấu trúc mô-đun discovery

Thư mục `network/udp` chứa phần phát hiện peer bằng UDP.
Bộ điều phối và các thành phần hỗ trợ nằm trực tiếp trong thư mục này.

```text
network/
├── udp/
│   ├── discovery_service.py # Điều phối start/stop, trạng thái và timeout
│   ├── broadcaster.py       # Phát presence định kỳ
│   ├── listener.py          # Nhận presence và cập nhật registry
│   ├── presence_protocol.py # Mã hóa/kiểm tra HELLO JSON UTF-8
│   └── peer_registry.py     # Lưu, tra cứu và loại peer hết hạn bằng Lock
└── tcp/
```

Console và giao diện chỉ cần import service:

```python
from network.udp.discovery_service import DiscoveryService
```

Luồng gửi: `DiscoveryService → UDPBroadcaster → PresenceProtocol → UDP`.
Luồng nhận: `UDP → UDPListener → PresenceProtocol → PeerRegistry`.
Service đọc registry qua `get_peer()`/`list_peers()` và định kỳ gọi
`remove_expired_peers()` để loại peer hết hạn.

Cách chia này áp dụng nguyên tắc một trách nhiệm (SRP) và kết hợp các đối
tượng có sẵn. Không thêm lớp cơ sở hay kế thừa khi chưa có nhu cầu thay thế
thành phần. API service và định dạng gói HELLO giữ nguyên. Import trực tiếp
từ file mô-đun nên không cần `__init__.py`.

Chạy riêng các unit test hiện có của UDP:

```powershell
python -X utf8 -B -m unittest discover -s tests -p test_presence_protocol.py -v
python -X utf8 -B -m unittest discover -s tests -p test_peer_registry.py -v
```

<!-- Khi nhận được thông tin của Minh, chương trình sẽ lưu ở đâu? Làm sao biết Minh là người mới, đã tồn tại, hay đã offline? Và người làm TCP sẽ lấy thông tin của Minh bằng cách nào? -->

<!-- 
PHẦN 3. Thiết kế PeerRegistry
3.1. Tại sao chúng ta cần PeerRegistry?
Giả sử trong mạng LAN có 3 người:
- Hoàng: 192.168.1.10
- Minh: 192.168.1.11
- Huy: 192.168.1.12
Hoàng đang chạy ứng dụng. Cứ 3 giây, Minh và Huy lại gửi thông báo UDP Presence. -->

<!-- Máy Hoàng sẽ liên tục nhận những thông báo như:
HELLO từ Minh
HELLO từ Huy
HELLO từ Minh
HELLO từ Huy
...


Nếu chương trình chỉ nhận rồi in ra màn hình:
print(message)



thì có một vấn đề: chương trình không ghi nhớ được những người đã phát hiện.

Khi người dùng muốn chat với Minh, TCP sẽ không có danh sách nào để tìm IP và port của Minh.

Vì vậy, chúng ta cần một thành phần chuyên quản lý thông tin peer.

Thành phần đó là PeerRegistry.
3.2. PeerRegistry chịu trách nhiệm những gì?
Trước hết, hãy hiểu rõ ranh giới trách nhiệm giữa các class.
Class	Trách nhiệm
PresenceProtocol	Chuyển đổi bytes và dữ liệu
UDPListener	Nhận các UDP packet
PeerRegistry	Quản lý danh sách peer
UDPBroadcaster	Gửi presence mỗi 3 giây
DiscoveryService	Điều phối các thành phần

PeerRegistry không gửi UDP packet và cũng không tạo socket.

Nó chỉ quản lý dữ liệu đã được UDPListener chuyển tới.
UDPListener

Nhận gói HELLO từ Minh

PresenceProtocol.decode()

Giải mã dữ liệu

PeerRegistry

Thêm, cập nhật, tìm kiếm và loại bỏ peer hết hạn

TCP / UI

Sử dụng thông tin peer đã được phát hiện


Đây là nguyên tắc phân chia trách nhiệm trong thiết kế OOP.

3.3. Thiết kế cấu trúc dữ liệu bên trong PeerRegistry
Chúng ta cần lưu nhiều đối tượng Peer.

Có hai phương án phổ biến: list hoặc dict.
Phương án A: Sử dụng list
online_users = [    Peer(username="minh", ...),    Peer(username="huy", ...)]



Cách này đơn giản nhưng nếu muốn tìm Minh, chương trình có thể phải duyệt từng phần tử.
Phương án B: Sử dụng dictionary
online_users = {    "minh": Peer(...),    "huy": Peer(...)}



Muốn lấy Minh:
peer = online_users["minh"]



Chương trình có thể truy cập trực tiếp theo username.

Mình chọn phương án B cho dự án của bạn.

Trong tuần 1, chúng ta tạm quy định mỗi username là duy nhất trong các peer được phát hiện. Nếu sau này cần hỗ trợ trùng username hoặc nhiều instance của cùng một tài khoản, chúng ta sẽ bổ sung peer_id.
3.4. Xác định hành vi của PeerRegistry
Một PeerRegistry cần thực hiện bốn hành vi chính.

1. Thêm hoặc cập nhật Peer — upsert_peer()

Nếu Minh chưa tồn tại thì thêm Minh. Nếu đã tồn tại thì cập nhật thông tin và thời điểm nhận presence gần nhất.




2. Tìm Peer — get_peer()

Tìm một người theo username và trả thông tin IP, TCP port cho phần TCP.




3. Liệt kê Peer — list_peers()

Trả về các peer hiện có để UI hiển thị danh sách online.




4. Xóa Peer hết hạn — remove_expired_peers()

Nếu quá 10 giây không nhận presence mới thì loại peer khỏi registry.



Lưu ý rằng trạng thái away vẫn có nghĩa là peer đang hoạt động. Chỉ khi không nhận presence đủ thời gian timeout, chúng ta mới xem peer là offline.

3.5. Hiểu last_seen trước khi code
Chúng ta giữ thiết kế theo đề gốc: presence mỗi 3 giây và timeout 10 giây.

Ví dụ Minh gửi presence vào các thời điểm:
Ví dụ về quá trình theo dõi Minh
Thời điểm	Hoạt động	Trạng thái Minh
0s	Nhận HELLO	Đang hoạt động
3s	Nhận HELLO	Đang hoạt động
6s	Nhận HELLO cuối	Đang hoạt động
9s	Không nhận thêm	Vẫn được giữ
12s	Không nhận thêm	Vẫn được giữ
16s	Đủ 10s từ HELLO cuối	Offline

Thời điểm kiểm tra được minh họa; việc loại bỏ thực tế diễn ra khi vòng kiểm tra timeout chạy.
Chúng ta sẽ dùng:
time.monotonic()



Để tính:
elapsed = now - peer.last_seen



Nếu:
elapsed >= 10



thì loại peer.

Tại sao không sử dụng number_no_responses như phương án trước?

Vì đề yêu cầu timeout theo thời gian thực, không phải số lượng gói đã mất. Sử dụng last_seen giúp chúng ta tuân thủ chính xác hơn.

3.6. Vấn đề đa luồng: Tại sao cần threading.Lock()?
Sau này có thể xuất hiện tình huống:
- Thread UDPListener đang thêm Minh.
- Thread kiểm tra timeout đang xóa Huy.
- Thread UI đang đọc danh sách peer.
Cả ba đều truy cập chung một dictionary.

Đây gọi là shared mutable state — trạng thái có thể thay đổi và được nhiều thread sử dụng.

Nếu không kiểm soát, dữ liệu có thể bị cập nhật không nhất quán.

Chúng ta sẽ dùng:
self._lock = threading.Lock()



Mỗi khi đọc hoặc sửa registry:
with self._lock:    ...



Như vậy tại một thời điểm, chỉ một thread được thực hiện đoạn thao tác được bảo vệ bởi cùng lock.

Chúng ta cũng sẽ tránh trả trực tiếp đối tượng Peer đang được lưu bên trong, để code bên ngoài không tự ý thay đổi nó mà bỏ qua lock. -->
