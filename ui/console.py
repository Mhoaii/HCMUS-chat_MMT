"""Console thử chat nhiều peer; GUI Tkinter giữ vùng soạn tin riêng tốt hơn."""
from uuid import uuid4

from chat.chat_manager import ChatManager


class Console:
    """Nhận lệnh người dùng và hiển thị sự kiện từ backend TCP/UDP."""

    def __init__(self, profile):
        """Nhận LocalProfile; trả None, tạo backend chưa khởi động."""
        self.backend = ChatManager(profile, self.emit)
        self.current = None
        self.unread = {}

    def emit(self, event, **data):
        """Nhận tên sự kiện/dữ liệu backend; in thông báo, trả None.

        Có thể được gọi từ thread mạng; không gọi input() trong callback.
        """
        if event == "message":
            username = data["username"]
            if username != self.current:
                self.unread[username] = self.unread.get(username, 0) + 1
            print(f"\n[{username}] {data['text']}", flush=True)
        elif event == "ack":
            print(f"\n[{data['message_id'][:8]}] {data['status']}", flush=True)
        elif event in ("error", "notice"):
            print(f"\n{data['message']}", flush=True)

    def run(self):
        """Không có đầu vào; mở backend, xử lý lệnh đến /quit/EOF/Ctrl+C; trả None."""
        try:
            self.backend.start()
            print("Lệnh: /list, /chat username, /msg username nội_dung, /leave,")
            print("      /online, /away, /quit. Trong hội thoại: nhập tin và Enter.")
            while True:
                command = input("> ").strip()
                if not command:
                    continue
                try:
                    if command == "/quit":
                        break
                    if command == "/list":
                        peers = self.backend.discovery.list_peers()
                        if not peers:
                            print("Chưa phát hiện peer. Chờ khoảng 3 giây rồi /list lại.")
                        for peer in peers:
                            print(f"{peer.username} | {peer.display_name} | "
                                  f"{peer.ip}:{peer.tcp_port} | {peer.status} | "
                                  f"chưa đọc: {self.unread.get(peer.username, 0)}")
                    elif command.startswith("/chat "):
                        username = command.split(maxsplit=1)[1]
                        if self.backend.discovery.get_peer(username) is None:
                            raise ValueError("Peer chưa xuất hiện trong LAN")
                        self.current = username
                        self.unread[username] = 0
                        print(f"Đang chat với {username}")
                    elif command == "/leave":
                        self.current = None
                    elif command in ("/online", "/away"):
                        self.backend.set_status(command[1:])
                    elif command.startswith("/msg "):
                        parts = command.split(maxsplit=2)
                        if len(parts) != 3:
                            raise ValueError("Cú pháp: /msg username nội_dung")
                        self.backend.send_message(parts[1], parts[2], uuid4().hex)
                    elif command.startswith("/"):
                        print("Lệnh chưa hỗ trợ")
                    elif self.current:
                        self.backend.send_message(self.current, command, uuid4().hex)
                    else:
                        print("Hãy chọn /chat username hoặc /msg username nội_dung")
                except (OSError, ValueError, RuntimeError) as error:
                    print(f"Lỗi: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nĐang thoát...")
        finally:
            self.backend.close()
