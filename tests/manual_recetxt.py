
import socket

from config import UDP_PORT
from network.udp.components.presence_protocol import PresenceProtocol


def main():
    """Nhận và in presence hợp lệ; bỏ gói lỗi, đóng socket khi ngắt bằng Ctrl+C."""
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
