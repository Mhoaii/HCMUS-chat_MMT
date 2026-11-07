
from models.peer import LocalProfile
from network.udp.broadcaster import UDPBroadcaster


def main():
    """Chạy thử bộ phát UDP bằng một hồ sơ cố định.

    Đầu vào: Không có tham số; chờ người dùng nhấn Enter qua input().
    Trả về: None sau khi dừng broadcaster trong finally.
    Đây là kiểm thử thủ công có phát dữ liệu mạng thật, không phải unit test.
    """
    profile = LocalProfile(
        username="hoang",
        display_name="Anh Hoàng",
        job_title="Marketing",
        tcp_port=5001,
        status="online"
    )

    broadcaster = UDPBroadcaster(profile)

    broadcaster.start()

    print("UDP Broadcaster started")
    print("Broadcasting every 3 seconds...")

    try:
        input("Nhấn Enter để dừng...\n")
    finally:
        broadcaster.stop()
        print("UDP Broadcaster stopped")


if __name__ == "__main__":
    main()
