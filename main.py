from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile
from network.udp.discovery_service import DiscoveryService
from pathlib import Path
from network.tcp.tcp_service import TCPChatService
from network.tcp.chat_session import ChatSessionService
from console_state import ConsoleState
from collections.abc import Callable
import sys


CONSOLE_HELP = """Các lệnh LAN Chat
/list                         Xem người dùng online và số thứ tự
/chat <username|số>            Mở hoặc chuyển sang cuộc chat được chọn
/chats                        Xem các hội thoại và số tin chưa đọc
/chat @username               Chọn tên trực tiếp, ví dụ @123 hoặc @@hoai cho @hoai
/accept [username]            Đồng ý lời mời; bỏ tên để chờ lời mời
/decline <username>           Từ chối lời mời chat
/send <đường dẫn>             Mời gửi file trong cuộc chat hiện tại
                             Dùng dấu ngoặc kép nếu đường dẫn có khoảng trắng
/acceptfile <mã>              Nhận file trong cuộc chat hiện tại
/declinefile <mã>             Từ chối file trong cuộc chat hiện tại
/status <online|away>         Đổi trạng thái quảng bá qua UDP
/leave                        Rời cuộc chat hiện tại
/help                         Xem hướng dẫn này
/quit                         Thoát ứng dụng
Nhập văn bản rồi Enter để gửi tin khi phiên chat đã được đồng ý."""


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
        if kind == "send_failed":
            print(f"Tin chưa gửi tới {username}: {data['text']}", flush=True)
    elif kind == "file_prepare_error":
        print(f"\nKhông thể chuẩn bị {data['path']}: {data['reason']}", flush=True)


def run_console(
    discovery: DiscoveryService | None,
    sessions: ChatSessionService,
    state: ConsoleState | None = None,
    read_line: Callable[[str], str] | None = None,
) -> None:
    """Đọc lệnh cho đến khi thoát. /send chỉ cần phiên chat đã mở."""
    state = state or ConsoleState(show_chat_event)
    read_line = read_line or input
    numbered_peers = {}
    print(CONSOLE_HELP)
    while True:
        try:
            line = read_line(state.prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            return
        current = state.current
        if not line:
            continue
        parts = line.split(maxsplit=1)
        command = parts[0]
        argument = parts[1] if len(parts) == 2 else ""
        try:
            if line == "/quit":
                return
            elif line == "/help":
                print(CONSOLE_HELP)
            elif line == "/chats":
                state.show_chats()
            elif line == "/leave":
                if not current:
                    print("Bạn chưa chọn cuộc chat.")
                    continue
                sessions.leave_chat(current)
                state.select("")
            elif command == "/send":
                if not current:
                    raise ValueError("Hãy mở một cuộc chat trước khi gửi file.")

                path = argument
                if path.startswith('"') and path.endswith('"'):
                    path = path[1:-1]

                if not path:
                    raise ValueError('Dùng /send "đường dẫn".')

                sessions.offer_file(current, Path(path), background=True)
                print("Đã xếp lời mời vào hàng gửi.")

            elif command in ("/acceptfile", "/declinefile"):
                if not current:
                    raise ValueError("Hãy chọn cuộc chat với người gửi file.")
                if not argument:
                    raise ValueError(f"Dùng {command} <mã lời mời>.")

                sessions.reply_file(current, argument, command == "/acceptfile")
                state.answered_file(current, argument)
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
                if not username:
                    raise ValueError("Dùng /chat <username|số>. Gõ /help để xem hướng dẫn.")
                if state.status(username) in ("ready", "accepting", "waiting", "connecting", "incoming"):
                    state.select(username)
                    continue
                peer = discovery.get_peer(username)
                if peer is None:
                    raise ValueError(f"Không tìm thấy {username} trong LAN. Gõ /list để cập nhật.")
                state.select(peer.username)
                try:
                    sessions.invite(peer)
                except (OSError, ValueError, RuntimeError):
                    state.select(current)
                    raise
            elif command == "/accept":
                if not argument:
                    argument = state.pending_invitation()
                if not sessions.accept_chat(argument):
                    raise ValueError("Không có lời mời chat từ người dùng này.")
                if state.status(argument) not in ("disconnected", "error", "declined", "expired"):
                    state.select(argument)
            elif command == "/decline" and argument:
                sessions.decline_chat(argument)
            elif command.startswith("/"):
                print("Lệnh không hợp lệ hoặc thiếu tham số. Gõ /help để xem hướng dẫn.")
            elif current:
                sessions.send_text(current, line)
            else:
                print("Hãy chọn người bằng /chat user hoặc /accept user.")
        except (OSError, ValueError, RuntimeError) as error:
            print(error)


def _main() -> None:
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
        state = ConsoleState(show_chat_event)
        read_line = None
        if sys.stdin.isatty():
            from prompt_toolkit import PromptSession
            prompt = PromptSession()
            state.invalidate = prompt.app.invalidate
            read_line = lambda _: prompt.prompt(state.prompt)
        sessions = ChatSessionService(profile, listener, state.on_event)
        discovery = DiscoveryService(profile)
        sessions.start()
        discovery.start()
        run_console(discovery, sessions, state, read_line)
    except (EOFError, KeyboardInterrupt):
        print("\nĐang thoát chương trình.")
    finally:
        if discovery is not None:
            discovery.stop()
        if sessions is None:
            listener.stop()
        else:
            sessions.stop()


def main() -> None:
    """Bảo vệ output nền và nội dung đang gõ trong phiên terminal tương tác."""
    if sys.stdin.isatty():
        from prompt_toolkit.patch_stdout import patch_stdout
        with patch_stdout():
            _main()
    else:
        _main()


if __name__ == "__main__":
    main()
