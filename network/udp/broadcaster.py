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
    """Phát hồ sơ qua UDP broadcast định kỳ bằng thread nền."""
    def __init__(self, profile: LocalProfile):
        """Lưu hồ sơ, cấu hình broadcast và cờ dừng; chưa chạy thread."""
        self._profile = profile 

        self._udp_port = UDP_PORT
        self._broadcast_ip = BROADCAST_IP

        self._interval = PRESENCE_INTERVAL

        self._stop_event = threading.Event()
        self._thread = None

    def start(self):

        """Chạy thread phát presence nếu chưa chạy; báo ValueError nếu cổng TCP sai."""
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
        """Mở socket broadcast và gửi HELLO theo chu kỳ cho tới khi có cờ dừng.
        In lỗi gửi gói; Event.wait() cho phép dừng sớm khi đang đợi."""
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
        """Đánh thức khoảng chờ và chờ thread phát dừng; gọi từ luồng điều phối."""
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()
            self._thread = None
