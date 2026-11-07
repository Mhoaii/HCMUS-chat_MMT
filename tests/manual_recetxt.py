
import socket

from config import UDP_PORT
from network.udp.presence_protocol import PresenceProtocol


def main():
    """Mở socket để xem các gói presence nhận được trong terminal.

    Đầu vào: Không có tham số; nhận UDP datagram tại UDP_PORT.
    Trả về: None khi thoát vòng nhận do ngoại lệ; socket luôn đóng ở finally.
    Bỏ gói decode không hợp lệ, in IP nguồn và thông tin gói hợp lệ.
    Vòng lặp không có lệnh thoát riêng; có thể ngắt bằng Ctrl+C.
    Đây là kiểm thử thủ công, không tự được unittest discover chạy.
    """
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    try:
        sock.bind(("0.0.0.0", UDP_PORT))

        print(f"Listening on UDP port {UDP_PORT}")

        while True:
            data, address = sock.recvfrom(4096)

            try:
                message = PresenceProtocol.decode(data)
            except ValueError:
                continue

            print("\nReceived from:", address[0])
            print("Username:", message["username"])
            print("TCP port:", message["tcp_port"])
            print("Status:", message["status"])

    finally:
        sock.close()


if __name__ == "__main__":
    main()
