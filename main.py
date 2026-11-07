from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile
from network.udp.discovery_service import DiscoveryService


def show_peers(discovery: DiscoveryService)  -> None:
    """
    Hiển thị danh sách peer đã phát hiện.

    Tham số:
        discovery (DiscoveryService):
            Service đang quản lý UDP Discovery.

    Trả về:
        None.

    Chức năng:
        1. Lấy danh sách peer từ DiscoveryService.
        2. Kiểm tra danh sách có rỗng không.
        3. In thông tin từng peer.

    Lưu ý:
        Hàm này chỉ hiển thị dữ liệu.
        Nó không trực tiếp nhận gói UDP.
    """

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
    """
    Hàm khởi động chương trình LAN Chat.

    Tham số:
        Không có.

    Trả về:
        None.

    Chức năng:
        1. Nhận thông tin người dùng từ bàn phím.
        2. Tạo đối tượng LocalProfile.
        3. Hiển thị thông tin người dùng.

    Lưu ý:
        Chưa khởi động UDPBroadcaster hoặc UDPListener.
        Các thành phần UDP được chạy thử riêng.
    """

    print("===== LAN CHAT P2P =====")

    # Bước 1: Nhập thông tin của người dùng.
    username = input("Nhập username: ").strip()
    display_name = input("Nhập tên hiển thị: ").strip()
    job_title = input("Nhập chức danh: ").strip()

    try:
        test_tcp_port = int(input("Nhập port test: ").strip())
    except ValueError:
        print("TCP port phải là số nguyên.")
        return
    if not 1 <= test_tcp_port <= 65535:
        print("TCP port phải nằm trong khoảng 1-65535.")
        return
    # Không cho phép username rỗng.
    if not username:
        print("Username không được để trống!")
        return

    # Bước 2: Tạo đối tượng lưu thông tin bản thân.
    profile = LocalProfile(
        username=username,
        display_name=display_name or username,
        job_title=job_title or "Nhân viên",
        tcp_port=test_tcp_port,
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
    print("Các lệnh: /list, /status online, ""/status away, /quit")

    try:
          # BƯỚC 5: Vòng lặp nhận lệnh.
        while True:
            command = input("\n> ").strip()

            if command == "/list":
                show_peers(discovery)

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
        # BƯỚC 6: Luôn dừng UDP khi thoát.
        discovery.stop()

        print("Đã dừng UDP Discovery.")
    

if __name__ == "__main__":
    main()
