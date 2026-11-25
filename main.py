from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile
from network.udp.discovery_service import DiscoveryService
from pathlib import Path
from network.tcp.tcp_service import TCPChatService
from network.tcp.chat_session import ChatSessionService


def show_peers(discovery: DiscoveryService) -> dict[str, str]:
    """In danh sách và trả ánh xạ số thứ tự sang username của đúng lượt hiển thị."""

    peers = discovery.list_peers()
    if not peers: 
        print("Chưa phát hiện người dùng nào. ")
        return {}
    print("\n===== DANH SÁCH NGƯỜI DÙNG ====")

    numbered = {}
    for number, peer in enumerate(peers, start=1):
        numbered[str(number)] = peer.username
        print(
            f"{number}. Username: {peer.username} | "
            f"Tên: {peer.display_name} | "
            f"IP: {peer.ip} | "
            f"TCP Port: {peer.tcp_port} | "
            f"Status: {peer.status}"
        )
    return numbered


def show_chat_event(kind: str, username: str, data: dict) -> None:
    """In sự kiện của service. Chỉ vòng lặp lệnh được đọc bàn phím."""
    if kind == "file_offer":
        transfer_id = data["transfer_id"]
        print(
            f"\n{username} muốn gửi {data['name']} ({data['size']} byte).\n"
            f"Trong cuộc chat với {username}, dùng một trong hai lệnh:\n"
            f"/acceptfile {transfer_id}\n"
            f"/declinefile {transfer_id}",
            flush=True,
        )
    elif kind == "file_reply":
        action = "đã đồng ý nhận" if data["accepted"] else "đã từ chối"
        print(f"\n{username} {action} {data['name']} ({data['transfer_id']}).",
              flush=True)
    elif kind == "message":
        print(f"\n{username}: {data['text']}", flush=True)
    elif kind == "file_progress":
        print(f"\n[{username}] {data['name']} · {data['percent']}%", flush=True)
    elif kind == "file_sent":
        print(f"\n100% · {username} đã lưu {data['name']}.", flush=True)
    elif kind == "file_received":
        print(f"\n100% · Đã lưu file từ {username} tại {data['path']}.", flush=True)
    elif kind == "file_error":
        print(f"\nLỗi truyền {data['name']}: {data['reason']}", flush=True)
    elif kind == "chat_state":
        state = data["state"]
        if state == "incoming":
            print(f"\n{username} mời chat. Gõ /accept {username} hoặc /decline {username}.", flush=True)
        else:
            print(f"\n[{username}] {state} {data.get('reason', '')}".rstrip(), flush=True)
    elif kind in ("network_error", "send_failed"):
        print(f"\nLỗi: {data['reason']}", flush=True)


def run_console(discovery: DiscoveryService | None, sessions: ChatSessionService) -> None:
    """Đọc lệnh cho đến khi thoát. /send chỉ cần phiên chat đã mở."""
    current = ""
    numbered_peers = {}
    print("/list | /status online|away | /chat <username|số> | /accept [user] | /decline user")
    print("/chat @username để chọn đúng tên, ví dụ @123 hoặc @@hoai cho tên @hoai")
    print('/send "đường dẫn" | /acceptfile <mã> | /declinefile <mã> | Nhập tin nhắn')
    print("/leave để rời cuộc chat | /quit để thoát ứng dụng")
    while True:
        line = input(f"[{current}] > " if current else "> ").strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        command = parts[0]
        argument = parts[1] if len(parts) == 2 else ""
        try:
            if line == "/quit":
                return
            elif line == "/leave":
                if not current:
                    print("Bạn chưa chọn cuộc chat.")
                    continue
                sessions.leave_chat(current)
                current = ""
            elif command == "/send":
                if not current:
                    raise ValueError("Hãy mở một cuộc chat trước khi gửi file.")

                path = argument
                if path.startswith('"') and path.endswith('"'):
                    path = path[1:-1]

                if not path:
                    raise ValueError('Dùng /send "đường dẫn".')

                sessions.offer_file(current, Path(path))
                print("Đã xếp lời mời vào hàng gửi.")

            elif command in ("/acceptfile", "/declinefile"):
                if not current:
                    raise ValueError("Hãy chọn cuộc chat với người gửi file.")
                if not argument:
                    raise ValueError(f"Dùng {command} <mã lời mời>.")

                sessions.reply_file(current, argument, command == "/acceptfile")
                print("Đã xếp phản hồi vào hàng gửi.")

            elif command == "/list" and discovery:
                numbered_peers = show_peers(discovery)
            elif command == "/status" and discovery:
                discovery.set_status(argument)
                print(f"Trạng thái: {argument}")
            elif command == "/chat" and discovery:
                username = argument
                if argument.isascii() and argument.isdecimal():
                    if argument not in numbered_peers:
                        raise ValueError("Số thứ tự chưa có. Gõ /list để xem danh sách.")
                    username = numbered_peers[argument]
                # @username cho phép chọn đích danh cả tài khoản có tên toàn số.
                elif argument.startswith("@"):
                    username = argument[1:]
                peer = discovery.get_peer(username)
                if peer is None:
                    raise ValueError(f"Không tìm thấy {username} trong LAN. Gõ /list để cập nhật.")
                sessions.invite(peer)
                current = peer.username
            elif command == "/accept":
                if not argument:
                    print("Đang chờ lời mời chat...", flush=True)
                    argument = sessions.wait_for_invitation()
                if not sessions.accept_chat(argument):
                    raise ValueError("Không có lời mời chat từ người dùng này.")
                current = argument
            elif command == "/decline" and argument:
                sessions.decline_chat(argument)
            elif command.startswith("/"):
                print("Lệnh không hợp lệ hoặc thiếu tham số.")
            elif current:
                sessions.send_text(current, line)
            else:
                print("Hãy chọn người bằng /chat user hoặc /accept user.")
        except (OSError, ValueError, RuntimeError) as error:
            print(error)


def main() -> None:
    """Mở listener, quảng bá cổng thực và dọn TCP/UDP khi console kết thúc."""
    print("===== LAN CHAT P2P =====")
    username = input("Nhập username: ").strip()
    name = input("Nhập tên hiển thị: ").strip() or username
    job = input("Nhập chức danh: ").strip() or "Nhân viên"
    listener = TCPChatService()
    port = listener.start(PORT_DEFAULT)
    sessions = None
    discovery = None
    try:
        profile = LocalProfile(username, name, job, port, DEFAULT_STATUS)
        print(f"{name} ({username}) | {job} | TCP {port} | {profile.status}")
        sessions = ChatSessionService(profile, listener, show_chat_event)
        discovery = DiscoveryService(profile)
        sessions.start()
        discovery.start()
        run_console(discovery, sessions)
    except (EOFError, KeyboardInterrupt):
        print("\nĐang thoát chương trình.")
    finally:
        if discovery is not None:
            discovery.stop()
        if sessions is None:
            listener.stop()
        else:
            sessions.stop()


if __name__ == "__main__":
    main()
