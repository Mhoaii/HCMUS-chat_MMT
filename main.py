from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile
from network.udp import DiscoveryService
import socket
from network.tcp.tcp_service import TCPChatService
from network.tcp.tcp_chat import chat, run_client
def show_peers(discovery: DiscoveryService)  -> None:
    """In danh sách peer từ DiscoveryService; báo nếu danh sách rỗng."""

    peers = discovery.list_peers()
    if not peers: 
        print("Chưa phát hiện người dùng nào. ")
        return
    print("\n===== DANH SÁCH NGƯỜI DÙNG ====")

    for peer in peers:
        print(
            f"Username: {peer.username} | "
            f"Tên: {peer.display_name} | "
            f"IP: {peer.ip} | "
            f"TCP Port: {peer.tcp_port} | "
            f"Status: {peer.status}"
        )


def main() -> None:
    """Nhập hồ sơ, mở TCP và UDP discovery rồi xử lý lệnh console.
    Dừng UDP khi thoát; listener TCP hiện chưa được đóng tại đây."""

    print("===== LAN CHAT P2P =====")

    # Bước 1: Nhập thông tin của người dùng.
    username = input("Nhập username: ").strip()
    display_name = input("Nhập tên hiển thị: ").strip()
    job_title = input("Nhập chức danh: ").strip()
    tcp = TCPChatService()
    actual_port = tcp.start(PORT_DEFAULT)
    

    # Bước 2: Tạo đối tượng lưu thông tin bản thân.
    profile = LocalProfile(
        username=username,
        display_name=display_name or username,
        job_title=job_title or "Nhân viên",
        tcp_port=actual_port,
        status=DEFAULT_STATUS
    )

    print("\n===== THÔNG TIN NGƯỜI DÙNG =====")
    print(f"Username: {profile.username}")
    print(f"Tên hiển thị: {profile.display_name}")
    print(f"Chức danh: {profile.job_title}")
    print(f"TCP Port: {profile.tcp_port}")
    print(f"Trạng thái: {profile.status}")

    #Bước 3: Tạo DiscoveryService.
    #Constructor chỉ khởi tạo các thành phần UDP
    discovery = DiscoveryService(profile)

     #Bước 4: Khời động UDP
    discovery.start()

    print("\nUDP Discovery đã khởi động.")
    print("Các lệnh: /list, /status online, ""/status away, /quit, ""/accept, /chat + username")

    try:
          # BƯỚC 5: Vòng lặp nhận lệnh.
        while True:
            command = input("\n> ").strip()

            if command == "/list":
                show_peers(discovery)

            elif command == "/accept": 
                print ("Đang chờ người kết nối TCP...")
                connection, address = tcp.accept()
                print(f"Đã kết nối với {address[0]}:{address[1]}")
                chat(connection)

            elif command.startswith("/chat "):
                username = command.split(maxsplit=1)[1]
                peer = discovery.get_peer(username)
                if peer is None:
                    print("Chưa tìm thấy người dùng này trong LAN.")
                else:
                    try:
                        run_client(peer.ip, peer.tcp_port)
                    except OSError as error:
                        print(f"Không thể kết nối: {error}")

            elif command.startswith("/status "):
                new_status = command.split(
                    maxsplit=1
                )[1]

                try:
                    discovery.set_status(new_status)

                    print(
                        f"Đã đổi trạng thái: {new_status}"
                    )

                except ValueError:
                    print(
                        "Trạng thái chỉ được là "
                        "online hoặc away."
                    )
            elif command == "/quit":
                print("Đang thoát chương trình...")
                break

            elif not command:
                continue

            else:
                print("Lệnh không hợp lệ.")

    except (KeyboardInterrupt, EOFError):
        print("\nĐang thoát chương trình...")

    finally:
        # Dừng UDP trước khi thoát vòng điều phối.
        discovery.stop()

        print("Đã dừng UDP Discovery.")
    

if __name__ == "__main__":
    main()
