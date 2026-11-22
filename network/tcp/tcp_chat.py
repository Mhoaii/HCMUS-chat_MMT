"""TCP ngày 1: kết nối, gửi/nhận qua callback và console thử nghiệm."""

import argparse
import socket
import threading
from collections.abc import Callable
from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile
from network.tcp.tcp_service import TCPChatService
from network.udp.discovery_service import DiscoveryService

def connect_peer(host: str, port: int) -> socket.socket:
    """Kết nối host:port hợp lệ và trả socket đang mở; bên gọi chịu đóng.

    Báo ValueError nếu cổng sai; đóng socket tạm và báo lại lỗi kết nối.
    """
    if not 1 <= port <= 65535:
        raise ValueError(
            "TCP port phải nằm trong khoảng 1..65535."
        )

    connection = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    try:
        # Timeout dành cho thao tác thiết lập kết nối.
        connection.settimeout(5.0)
        connection.connect((host, port))

        # Sau khi kết nối, cho phép chờ tin liên tục.
        connection.settimeout(None)

    except Exception:
        connection.close()
        raise

    return connection


def send_message(
    connection: socket.socket,
    text: str,
) -> None:
    """Gửi text UTF-8 kèm newline; báo OSError nếu gửi thất bại."""
    packet = (text + "\n").encode("utf-8")
    connection.sendall(packet)


def receive_messages(
    connection: socket.socket,
    on_message: Callable[[str], None],
    on_disconnect: Callable[[], None],
) -> None:
    """Nhận tin newline và gọi callback trong luồng đang chạy hàm.

    Trả None khi EOF/lỗi socket; bên gọi chịu trách nhiệm đóng socket.
    """
    buffer = b""

    try:
        while True:
            try:
                data = connection.recv(4096)

            except OSError:
                break

            # Peer đã đóng chiều gửi hoặc đóng kết nối.
            if not data:
                break

            buffer += data

            # Một recv có thể chứa một phần tin hoặc nhiều tin.
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)

                on_message(
                    line.decode(
                        "utf-8",
                        errors="replace",
                    )
                )

        # Giữ cách xử lý dữ liệu cuối như bản console ban đầu.
        if buffer:
            on_message(
                buffer.decode(
                    "utf-8",
                    errors="replace",
                )
            )

    finally:
        on_disconnect()


def chat(connection: socket.socket) -> None:
    """Chạy console bằng API TCP chung; dọn socket/thread khi thoát."""

    def show_message(text: str) -> None:
        """In tin nhận được lên console; trả None."""
        print(
            f"\nPeer: {text}\nYou: ",
            end="",
            flush=True,
        )

    def show_disconnect() -> None:
        """Thông báo vòng nhận đã kết thúc; trả None."""
        print("\nVòng nhận tin đã kết thúc.")

    print("Connected. Type /quit to leave.")

    receiver = threading.Thread(
        target=receive_messages,
        args=(
            connection,
            show_message,
            show_disconnect,
        ),
        name="TCP-Console-Receiver",
        daemon=True,
    )
    receiver.start()

    try:
        while True:
            message = input("You: ")

            if message.strip() == "/quit":
                break

            if message:
                send_message(connection, message)

    except OSError as error:
        print(f"\nConnection closed: {error}")

    except (KeyboardInterrupt, EOFError):
        print("\nLeaving chat.")

    finally:
        # Đánh thức thread đang chờ recv trước khi đóng socket.
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        connection.close()
        receiver.join(timeout=1.0)


def run_server(host: str, port: int) -> None:
    """Lắng nghe host:port, nhận một kết nối rồi chạy console."""
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as server:
        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        server.bind((host, port))
        server.listen(1)

        actual_port = server.getsockname()[1]
        print(
            f"Waiting for a connection on "
            f"{host}:{actual_port}..."
        )

        connection, address = server.accept()

        with connection:
            print(
                f"Connected to "
                f"{address[0]}:{address[1]}"
            )
            chat(connection)


def run_client(host: str, port: int) -> None:
    """Kết nối host:port rồi chạy console; báo lỗi cho bên gọi."""
    with connect_peer(host, port) as connection:
        print(f"Connected to {host}:{port}")
        chat(connection)


def main() -> None:
    """Đọc tham số cho bản TCP độc lập và chạy server/client."""
    parser = argparse.ArgumentParser(
        description="TCP chat console demo."
    )

    subparsers = parser.add_subparsers(
        dest="role",
        required=True,
    )

    server_parser = subparsers.add_parser(
        "server",
        help="Chờ một client.",
    )
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=5000,
    )

    client_parser = subparsers.add_parser(
        "client",
        help="Kết nối tới server.",
    )
    client_parser.add_argument(
        "--host",
        required=True,
    )
    client_parser.add_argument(
        "--port",
        type=int,
        default=5000,
    )

    args = parser.parse_args()

    try:
        if args.role == "server":
            run_server(args.host, args.port)
        else:
            run_client(args.host, args.port)

    except (OSError, ValueError, OverflowError) as error:
        print(f"TCP error: {error}")

    except KeyboardInterrupt:
        print("\nĐã dừng TCP demo.")


if __name__ == "__main__":
    main()