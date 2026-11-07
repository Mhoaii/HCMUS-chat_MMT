# UDPBroadcaster
# │
# ├── Thuộc tính
# │   ├── _profile
# │   ├── _udp_port
# │   ├── _broadcast_ip
# │   ├── _interval
# │   ├── _thread
# │   └── _stop_event
# │
# └── Phương thức
#     ├── __init__()
#     ├── start()
#     ├── _run()
#     └── stop()


# Tạo UDP Socket
# sock = socket.socket(    socket.AF_INET,    socket.SOCK_DGRAM)
# Nếu muốn tạo TCP socket, thông thường chúng ta sử dụng SOCK_STREAM thay vì SOCK_DGRAM.

# Cho phép gửi Broadcast
# sock.setsockopt(    socket.SOL_SOCKET,    socket.SO_BROADCAST,    1)

#  gửi packet bằng sendto(packet, ("255.255.255.255", 999))

import socket
import threading

from config import(
    UDP_PORT,
    BROADCAST_IP,
    PRESENCE_INTERVAL
)

from models.peer import LocalProfile
from network.udp.presence_protocol import PresenceProtocol

class UDPBroadcaster:
    """Định kỳ phát hồ sơ của mình tới địa chỉ UDP broadcast trong LAN.

    Giữ tham chiếu LocalProfile, sử dụng PresenceProtocol và chứa Event/Thread.
    Đây là quan hệ chứa/sử dụng, không kế thừa các lớp đó.
    Thread nền giúp việc gửi định kỳ không chặn luồng nhập liệu chính.
    """
    def __init__(self, profile: LocalProfile):
        """Chuẩn bị dữ liệu và trạng thái dừng cho bộ phát.

        Đầu vào: profile (LocalProfile), hồ sơ dùng chung với DiscoveryService.
        Trả về: None. Chưa mở socket và chưa khởi động thread.
        Địa chỉ, cổng UDP và chu kỳ gửi lấy từ config.
        """
        self._profile = profile 

        self._udp_port = UDP_PORT
        self._broadcast_ip = BROADCAST_IP

        self._interval = PRESENCE_INTERVAL

        self._stop_event = threading.Event()
        self._thread = None

    def start(self):

        """Tạo và chạy thread phát presence, hoặc bỏ qua nếu thread đang chạy.

        Đầu vào: Không có tham số ngoài self.
        Trả về: None; việc phát gói diễn ra trong thread nền.
        Ngoại lệ: ValueError nếu tcp_port nằm ngoài 1..65535.
        Chỉ kiểm tra giá trị cổng, không kiểm chứng TCP server thực sự lắng nghe.
        Lỗi phát sinh bên trong thread không tự truyền về bên gọi start().
        """
        if self._thread is not None and self._thread.is_alive():
            return

        if not 1<= self._profile.tcp_port <= 65535:
            raise ValueError(
                "TCP server must have a valid listening port"
            )

        self._stop_event.clear()

        self._thread = threading.Thread(
            target = self._run,
            name = "UDP-Broadcaster",
            daemon = True
        )


        self._thread.start()


    def _run(self):
        """Vòng lặp nội bộ chạy trong thread UDP-Broadcaster.

        Đầu vào: Không có tham số ngoài self; đọc hồ sơ và cấu hình đã lưu.
        Trả về: None khi nhận yêu cầu dừng; socket được đóng bởi khối with.
        Mở UDP/IPv4, bật SO_BROADCAST, encode hồ sơ và sendto() theo chu kỳ.
        Event.wait(interval) vừa đợi vừa cho phép stop() đánh thức sớm.
        OSError/ValueError trong vòng gửi được in ra; lỗi tạo/cấu hình socket
        nằm ngoài khối try của vòng lặp.
        """
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        ) as udp_socket:

            udp_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_BROADCAST,
                1
            )

            while not self._stop_event.is_set():
                try:
                    packet = PresenceProtocol.encode(self._profile)

                    udp_socket.sendto(
                        packet, 
                        (
                            self._broadcast_ip,
                            self._udp_port
                        )
                    )

                except(OSError, ValueError) as error:
                    print(f"[UDP] Broadcast error: {error}")
                self._stop_event.wait(self._interval)

    def stop(self):
        """Yêu cầu bộ phát dừng và chờ thread kết thúc.

        Đầu vào: Không có tham số ngoài self.
        Trả về: None. Event.set() đánh thức khoảng chờ; join() chờ worker dừng.
        Gọi từ luồng điều phối, không gọi ngay trong chính thread bộ phát.
        """
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()
            self._thread = None