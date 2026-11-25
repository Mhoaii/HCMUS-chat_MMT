import io
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

from main import run_console, show_chat_event
from models.peer import Peer
from console_state import ConsoleState


class ConsoleEventTests(unittest.TestCase):
    """Kiểm tra callback hiển thị mà terminal truyền cho ChatSessionService."""

    def test_switch_replays_background_messages_without_reinvite(self):
        """Chuyển phiên TCP sẵn có phát lại tin nền và xóa số chưa đọc."""
        state = ConsoleState(show_chat_event)
        sessions, discovery = Mock(), Mock()
        with redirect_stdout(io.StringIO()) as output:
            state.on_event("chat_state", "hoai", {"state": "ready"})
            state.on_event("chat_state", "minh", {"state": "ready"})
            state.select("hoai")
            state.on_event("message", "minh", {"text": "tin một"})
            state.on_event("message", "minh", {"text": "tin hai"})
            self.assertNotIn("minh: tin một", output.getvalue())
            commands = ["/chats", "/chat minh", "/chats", "trả lời", "/quit"]
            with patch("builtins.input", side_effect=commands):
                run_console(discovery, sessions, state)
        self.assertIn("minh | ready | 2 tin chưa đọc", output.getvalue())
        self.assertIn("minh | ready | 0 tin chưa đọc", output.getvalue())
        self.assertIn("minh: tin một", output.getvalue())
        self.assertIn("minh: tin hai", output.getvalue())
        sessions.invite.assert_not_called()
        discovery.get_peer.assert_not_called()
        sessions.send_text.assert_called_once_with("minh", "trả lời")

    def test_disconnect_resets_prompt_but_keeps_other_chats(self):
        """Ngắt phiên hiện tại trả prompt chính, giữ lịch sử các phiên khác."""
        state = ConsoleState(show_chat_event)
        with redirect_stdout(io.StringIO()) as output:
            state.select("hoai")
            state.on_event("message", "minh", {"text": "chờ nhé"})
            state.on_event("chat_state", "minh", {"state": "disconnected"})
            self.assertEqual(state.prompt(), "[hoai] > ")
            state.on_event("chat_state", "hoai", {"state": "expired"})
            self.assertEqual(state.prompt(), "> ")
            state.select("minh")
        self.assertIn("minh: chờ nhé", output.getvalue())

    def test_accept_without_name_keeps_command_loop_responsive(self):
        """Không chờ vô hạn khi chưa có lời mời; /accept chọn lời mời đã đến."""
        state = ConsoleState(show_chat_event)
        sessions = Mock()

        def commands():
            """Mô phỏng lời mời đến giữa hai lần nhập lệnh."""
            yield "/accept"
            state.on_event("chat_state", "hoai", {"state": "incoming"})
            yield "/accept"
            yield "/quit"

        with patch("builtins.input", side_effect=commands()), redirect_stdout(io.StringIO()) as output:
            run_console(None, sessions, state)
        sessions.accept_chat.assert_called_once_with("hoai")
        sessions.wait_for_invitation.assert_not_called()
        self.assertIn("Chưa có lời mời chat", output.getvalue())
        self.assertEqual(state.current, "hoai")

    def test_prompt_preserves_typed_text_when_background_event_arrives(self):
        """Nhận tin và đóng chat trong lúc gõ vẫn trả đúng nội dung đã nhập."""
        import threading
        import time
        from prompt_toolkit import PromptSession
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit.application import create_app_session

        state = ConsoleState(show_chat_event)
        errors = []
        with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()), redirect_stdout(io.StringIO()), patch_stdout():
            prompt = PromptSession(input=keyboard, output=DummyOutput())
            state.invalidate = prompt.app.invalidate
            state.select("hoai")

            def receive_while_typing():
                """Chờ buffer có chữ rồi phát callback mạng trước phím Enter."""
                try:
                    deadline = time.monotonic() + 3
                    while prompt.default_buffer.text != "đang gõ":
                        if time.monotonic() > deadline:
                            raise AssertionError("Không đọc được dòng đang gõ")
                        time.sleep(0.01)
                    state.on_event("message", "hoai", {"text": "xin chào"})
                    state.on_event("chat_state", "hoai", {"state": "disconnected"})
                    self.assertEqual(prompt.default_buffer.text, "đang gõ")
                except BaseException as error:
                    errors.append(error)
                finally:
                    keyboard.send_text("\r")

            worker = threading.Thread(target=receive_while_typing)
            worker.start()
            keyboard.send_text("đang gõ")
            result = prompt.prompt(state.prompt)
            worker.join(timeout=4)
        self.assertEqual(errors, [])
        self.assertEqual(result, "đang gõ")
        self.assertEqual(state.prompt(), "> ")

    def test_help_and_invalid_command_do_not_send_messages(self):
        """/help in lại cú pháp; lệnh sai nhắc trợ giúp và vòng nhập tiếp tục."""
        sessions, discovery = Mock(), Mock()
        commands = ["/chat hoai", "/help", "/unknown", "/quit"]
        with patch("builtins.input", side_effect=commands), redirect_stdout(io.StringIO()) as output:
            run_console(discovery, sessions)
        self.assertEqual(output.getvalue().count("Các lệnh LAN Chat"), 2)
        for command in ("/list", "/chat", "/send", "/leave", "/status", "/help", "/quit"):
            self.assertIn(command, output.getvalue())
        self.assertIn("Gõ /help", output.getvalue())
        sessions.send_text.assert_not_called()
        sessions.leave_chat.assert_not_called()

    def test_chat_number_uses_last_displayed_list(self):
        """Peer rời LAN không làm số cũ trỏ sang người mới cho tới lượt /list sau."""
        sessions, discovery = Mock(), Mock()
        hoai = Peer("hoai", "Hoài", "SV", "127.0.0.1", "away", 0, 5001)
        minh = Peer("123", "Minh", "SV", "127.0.0.1", "online", 0, 5002)
        live = {hoai.username: hoai}
        discovery.list_peers.side_effect = lambda: list(live.values())
        discovery.get_peer.side_effect = live.get

        def commands():
            yield "/chat 1"
            yield "/list"
            yield "/chat 1"
            live.clear()
            live[minh.username] = minh
            yield "/chat 1"
            yield "/list"
            yield "/chat 1"
            yield "/chat @123"
            live.clear()
            yield "/list"
            yield "/chat 1"
            yield "/quit"

        with patch("builtins.input", side_effect=commands()), redirect_stdout(io.StringIO()) as output:
            run_console(discovery, sessions)
        self.assertEqual([c.args[0] for c in sessions.invite.call_args_list], [hoai, minh, minh])
        self.assertIn("1. Username: hoai", output.getvalue())
        self.assertIn("Không tìm thấy hoai", output.getvalue())

    def test_chat_explicit_username_with_at_prefix(self):
        """Tiền tố @ chọn username trực tiếp, kể cả tên bắt đầu bằng @."""
        sessions, discovery = Mock(), Mock()
        peer = Peer("@hoai", "Hoài", "SV", "127.0.0.1", "online", 0, 5001)
        discovery.get_peer.return_value = peer
        with patch("builtins.input", side_effect=["/chat @@hoai", "/quit"]), patch("builtins.print"):
            run_console(discovery, sessions)
        discovery.get_peer.assert_called_once_with("@hoai")
        sessions.invite.assert_called_once_with(peer)

    def test_leave_returns_to_prompt_and_quit_exits_active_chat(self):
        """Rời chat trả về prompt chính, còn /quit trong chat kết thúc ngay."""
        sessions = Mock()
        discovery = Mock()
        discovery.get_peer.return_value.username = "hoai"
        commands = ["/leave", "/chat hoai", "/leave", "/chat hoai", "/quit"]
        with patch("builtins.input", side_effect=commands) as keyboard, patch("builtins.print"):
            run_console(discovery, sessions)
        prompts = [call.args[0] for call in keyboard.call_args_list]
        self.assertEqual(prompts, ["> ", "> ", "[hoai] > ", "> ", "[hoai] > "])
        sessions.leave_chat.assert_called_once_with("hoai")
        sessions.send_text.assert_not_called()

    def test_file_reply_then_chat_message(self):
        """Mỗi quyết định về file được in và terminal vẫn hiển thị tin tiếp theo."""
        for accepted, expected in ((True, "đã đồng ý nhận"), (False, "đã từ chối")):
            with self.subTest(accepted=accepted), redirect_stdout(io.StringIO()) as output:
                show_chat_event("file_reply", "hoai", {
                    "transfer_id": "a" * 32, "name": "README.md", "accepted": accepted,
                })
                show_chat_event("message", "hoai", {"text": "Mình vẫn đang chat"})
                lines = output.getvalue().splitlines()
                self.assertIn(f"hoai {expected} README.md ({'a' * 32}).", lines)
                self.assertIn("hoai: Mình vẫn đang chat", lines)
