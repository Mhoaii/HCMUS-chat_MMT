"""Điểm vào: python main.py (console) hoặc python main.py --gui (Tkinter)."""

import argparse

from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile


def main():
    """Đọc tùy chọn CLI/hồ sơ và chạy chat TCP + UDP.

    Đầu vào: Không có tham số Python; nhận --gui/--username/--port/--name/--job.
    Trả về: None sau khi đóng chương trình. Lỗi hồ sơ/cổng được in ra console.
    """
    parser = argparse.ArgumentParser(description="LAN Chat UDP discovery + TCP chat")
    parser.add_argument("--gui", action="store_true", help="Mở giao diện Tkinter")
    parser.add_argument("--username")
    parser.add_argument("--name")
    parser.add_argument("--job")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.gui:
        from ui.app import main as gui_main
        gui_main()
        return
    print("===== LAN CHAT P2P =====")

    username = (args.username if args.username is not None else input("Nhập username: ")).strip()

    display_name = (args.name if args.name is not None else input("Nhập tên hiển thị: ")).strip()

    job_title = (args.job if args.job is not None else input("Nhập chức danh: ")).strip()

    try:
        test_port = args.port if args.port is not None else int(input("Nhập tcp_port: ").strip())
        if not username or len(username) > 128:
            raise ValueError("Username phải có 1..128 ký tự")
        profile = LocalProfile(
            username=username,
            display_name=display_name or username,
            job_title=job_title or "Nhân viên",
            tcp_port=test_port,
            status=DEFAULT_STATUS
        )
    except ValueError:
        print("Hồ sơ không hợp lệ: kiểm tra username, trạng thái và TCP port (1..65535).")
        return

    print("\n===== THÔNG TIN NGƯỜI DÙNG =====")
    print(f"Username: {profile.username}")
    print(f"Tên hiển thị: {profile.display_name}")
    print(f"Chức danh: {profile.job_title}")
    print(f"TCP Port: {profile.tcp_port}")
    print(f"Trạng thái: {profile.status}")
    from ui.console import Console
    try:
        Console(profile).run()
    except (OSError, RuntimeError) as error:
        print(f"Không thể khởi động LAN Chat: {error}")


if __name__ == "__main__":
    main()
