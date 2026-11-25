import io
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

from main import run_console, show_chat_event
from models.peer import Peer


class ConsoleEventTests(unittest.TestCase):
    """Kiểm tra callback hiển thị mà terminal truyền cho ChatSessionService."""

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
