
from models.peer import LocalProfile
from network.udp.components.udp_broadcaster import UDPBroadcaster


def main():
    """Phát presence mẫu qua mạng thật; nhấn Enter để dừng và dọn broadcaster."""
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
