"""Kiểm thử lời mời và UI bằng socket TCP thật trên loopback."""

import json
import queue
import socket
import threading
import time
import unittest
from unittest.mock import patch

from models.peer import LocalProfile, Peer
from network.tcp.chat_session import ChatSessionService, PROTOCOL
from network.tcp.tcp_service import TCPChatService
from ui.app import ChatWindow


class ChatSessionTests(unittest.TestCase):
    """Kiểm tra giao thức, cạnh tranh kết nối và thu hồi worker/socket."""

    def setUp(self) -> None:
        """Mở hai listener riêng; ghi sự kiện mà không sử dụng Tk."""
        self.services = []
        self.events = {}
        self.worker_errors = []
        self.old_hook = threading.excepthook
        threading.excepthook = lambda args: self.worker_errors.append(args.exc_value)
        self.a = self.make_service("a")
        self.b = self.make_service("b")

    def tearDown(self) -> None:
        """Dừng mọi service và xác nhận không rò reader/writer."""
        try:
            for service in self.services:
                service.stop()
            self.assertTrue(all(not s._workers and not s._sockets for s in self.services))
            self.assertEqual(self.worker_errors, [])
        finally:
            threading.excepthook = self.old_hook

    def make_service(self, username: str, **options) -> ChatSessionService:
        """Tạo service thật trên cổng trống và hàng sự kiện thread-safe."""
        listener = TCPChatService()
        profile = LocalProfile(username, username.upper(), "SV", listener.start(0))
        events = queue.Queue()
        service = ChatSessionService(
            profile, listener, lambda *event: events.put(event), **options,
        )
        self.events[username] = events
        self.services.append(service)
        service.start()
        return service

    @staticmethod
    def peer(service: ChatSessionService) -> Peer:
        """Chuyển hồ sơ thành endpoint loopback, gồm trạng thái away hợp lệ."""
        p = service.profile
        return Peer(p.username, p.display_name, "SV", "127.0.0.1", "away",
                    time.monotonic(), p.tcp_port)

    def wait(self, predicate, timeout: float = 3) -> None:
        """Chờ điều kiện có hạn; thất bại thay vì treo test."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        self.assertTrue(predicate(), "Hết thời gian chờ điều kiện TCP")

    @staticmethod
    def state(service: ChatSessionService, username: str) -> str:
        """Đọc trạng thái dưới cùng khóa mà worker sử dụng."""
        with service._lock:
            link = service._links.get(username)
            return link.state if link else "closed"

    def accept_pair(self, a: ChatSessionService, b: ChatSessionService) -> None:
        """Mời rồi đồng ý; xác nhận cả hai đầu dùng trạng thái ready."""
        a.invite(self.peer(b))
        self.wait(lambda: self.state(b, a.profile.username) == "incoming")
        b.accept_chat(a.profile.username)
        self.wait(lambda: self.state(a, b.profile.username) == "ready"
                  and self.state(b, a.profile.username) == "ready")

    def wait_event(self, username: str, kind: str) -> tuple:
        """Lấy đúng loại sự kiện từ queue, bỏ qua các trạng thái trước đó."""
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                event = self.events[username].get(timeout=0.1)
            except queue.Empty:
                continue
            if event[0] == kind:
                return event
        self.fail(f"Không nhận được sự kiện {kind}")

    def test_invitation_required_and_bidirectional_unicode(self) -> None:
        """Chặn gửi trước đồng ý; sau đó chat Unicode và nội dung giống lệnh."""
        self.a.invite(self.peer(self.b))
        self.wait(lambda: self.state(self.b, "a") == "incoming")
        with self.assertRaises(RuntimeError):
            self.a.send_text("b", "chưa được đồng ý")
        self.b.accept_chat("a")
        self.wait(lambda: self.state(self.a, "b") == self.state(self.b, "a") == "ready")
        text = "Xin chào Hoài 👋\nACCEPT\n{\"type\":\"decline\"}"
        self.a.send_text("b", text)
        self.assertEqual(self.wait_event("b", "message")[2]["text"], text)
        self.b.send_text("a", "Hoài trả lời")
        self.assertEqual(self.wait_event("a", "message")[2]["text"], "Hoài trả lời")
        with self.assertRaises(ValueError):
            self.a.send_text("b", "   ")
        with self.assertRaises(ValueError):
            self.a.send_text("b", "a" * 16_001)

    def test_decline_and_reinvite(self) -> None:
        """Từ chối giải phóng cả hai socket; mời lại vẫn hoạt động."""
        self.a.invite(self.peer(self.b))
        self.wait(lambda: self.state(self.b, "a") == "incoming")
        self.b.decline_chat("a")
        self.wait(lambda: self.state(self.a, "b") == self.state(self.b, "a") == "closed")
        self.accept_pair(self.a, self.b)

    def test_timeout_and_disconnect_cleanup(self) -> None:
        """Lời mời hết hạn và peer đóng đều thu hồi kết nối."""
        self.a.invite_timeout = 0.2
        self.a.invite(self.peer(self.b))
        self.wait(lambda: self.state(self.b, "a") == "incoming")
        self.wait(lambda: self.state(self.a, "b") == self.state(self.b, "a") == "closed")
        self.a.invite_timeout = 30
        self.accept_pair(self.a, self.b)
        self.b.stop()
        self.wait(lambda: self.state(self.a, "b") == "closed")

    def test_simultaneous_invitations_keep_one_connection(self) -> None:
        """Hai lời mời cùng lúc hội tụ về một socket hai chiều."""
        from network.tcp.tcp_chat import connect_peer
        barrier = threading.Barrier(2)

        def connect_together(host: str, port: int) -> socket.socket:
            """Giữ cả hai worker cho tới khi hai lời mời đều được tạo."""
            barrier.wait(timeout=2)
            return connect_peer(host, port)

        with patch("network.tcp.chat_session.connect_peer", connect_together):
            self.a.invite(self.peer(self.b))
            self.b.invite(self.peer(self.a))
            self.wait(lambda: self.state(self.a, "b") == self.state(self.b, "a") == "ready")
        self.wait(lambda: len(self.a._sockets) == len(self.b._sockets) == 1)
        self.assertEqual(self.a._links["b"].request_id, self.b._links["a"].request_id)
        self.a.send_text("b", "một kết nối")
        self.assertEqual(self.wait_event("b", "message")[2]["text"], "một kết nối")

    def test_multiple_peers_on_same_ip(self) -> None:
        """Ba peer cùng IP vẫn phân biệt theo danh tính trong lời mời."""
        c = self.make_service("c")
        self.accept_pair(self.a, self.b)
        self.accept_pair(c, self.b)
        self.a.send_text("b", "từ A")
        c.send_text("b", "từ C")
        received = {self.wait_event("b", "message")[1] for _ in range(2)}
        self.assertEqual(received, {"a", "c"})

    def test_connect_failure_and_writer_failure(self) -> None:
        """Lỗi connect/gửi không treo worker và trả lại nội dung chưa gửi."""
        with socket.socket() as unavailable:
            unavailable.bind(("127.0.0.1", 0))
            port = unavailable.getsockname()[1]
            self.a.invite(Peer("offline", "Offline", "SV", "127.0.0.1",
                               "away", time.monotonic(), port))
            self.wait(lambda: self.state(self.a, "offline") == "closed")
        self.accept_pair(self.a, self.b)
        from network.tcp.tcp_chat import send_message

        def fail_message(connection: socket.socket, text: str) -> None:
            """Gây lỗi riêng ở tin chat, giữ nguyên các gói điều khiển."""
            if json.loads(text)["type"] == "message":
                raise OSError("Lỗi gửi dùng trong test")
            send_message(connection, text)

        with patch("network.tcp.chat_session.send_message", fail_message):
            self.a.send_text("b", "Nội dung cần giữ")
            event = self.wait_event("a", "send_failed")
            self.assertEqual(event[2]["text"], "Nội dung cần giữ")
            self.wait(lambda: self.state(self.a, "b") == self.state(self.b, "a") == "closed")

    def test_completed_send_is_recorded_even_if_eof_arrives_first(self) -> None:
        """EOF ngay sau sendall không làm biến mất tin đã gửi khỏi lịch sử local."""
        self.accept_pair(self.a, self.b)
        from network.tcp.tcp_chat import send_message
        link = self.a._links["b"]

        def send_then_disconnect(connection: socket.socket, text: str) -> None:
            """Cho reader kết thúc trước khi writer kịp phát sự kiện sent."""
            send_message(connection, text)
            if json.loads(text)["type"] == "message":
                self.a._drop(link, "EOF mô phỏng ngay sau gửi")

        with patch("network.tcp.chat_session.send_message", send_then_disconnect):
            self.a.send_text("b", "Tin vừa gửi")
            self.assertEqual(self.wait_event("a", "sent")[2]["text"], "Tin vừa gửi")

    def test_malformed_connection_does_not_stop_listener(self) -> None:
        """Dữ liệu sai chỉ đóng socket lỗi; listener còn nhận lời mời mới."""
        with socket.create_connection(("127.0.0.1", self.b.profile.tcp_port)) as raw:
            raw.settimeout(2)
            raw.sendall(b"not-json\n")
            self.assertEqual(raw.recv(1), b"")
        self.accept_pair(self.a, self.b)

    def test_fragmented_request_and_coalesced_messages(self) -> None:
        """Phân mảnh UTF-8 và gộp nhiều gói không làm lẫn nội dung."""
        import uuid
        request_id = uuid.uuid4().hex
        packet = dict(protocol=PROTOCOL, request_id=request_id, type="request",
                      username="raw", display_name="Người thử 👋", tcp_port=12345, to="b")
        with socket.create_connection(("127.0.0.1", self.b.profile.tcp_port)) as raw:
            raw.settimeout(2)
            data = (json.dumps(packet, ensure_ascii=False) + "\n").encode()
            for start in range(0, len(data), 3):
                raw.sendall(data[start:start + 3])
            self.wait(lambda: self.state(self.b, "raw") == "incoming")
            self.b.accept_chat("raw")
            self.assertIn(b'"accept"', raw.recv(4096))
            messages = [dict(protocol=PROTOCOL, request_id=request_id,
                             type="message", text=f"Tin {i} 👋") for i in range(3)]
            raw.sendall("".join(json.dumps(p) + "\n" for p in messages).encode())
            received = [self.wait_event("b", "message")[2]["text"] for _ in range(3)]
            self.assertEqual(received, [f"Tin {i} 👋" for i in range(3)])

    def test_close_unidentified_socket_and_late_connect(self) -> None:
        """Dừng service thu hồi socket chưa có lời mời và kết quả connect muộn."""
        with socket.create_connection(("127.0.0.1", self.b.profile.tcp_port)) as raw:
            self.wait(lambda: bool(self.b._sockets))
            self.b.stop()
            raw.settimeout(2)
            self.assertEqual(raw.recv(1), b"")
        started, release = threading.Event(), threading.Event()
        late = socket.socket()

        def late_connect(host: str, port: int) -> socket.socket:
            """Mô phỏng connect trả về sau khi UI đã đóng."""
            started.set()
            release.wait(3)
            return late

        with patch("network.tcp.chat_session.connect_peer", late_connect):
            self.a.invite(self.peer(self.b))
            self.assertTrue(started.wait(1))
            self.a.stop()
            release.set()
            self.wait(lambda: late.fileno() == -1 and not self.a._workers)


class ChatWindowTests(unittest.TestCase):
    """Gọi widget thật trên luồng chính; mạng giữa các cửa sổ là TCP thật."""

    def setUp(self) -> None:
        """Tạo ba cửa sổ ẩn và cung cấp snapshot discovery cố định cho UI."""
        self.apps = []
        self.errors = []
        for name in ("Hoàng", "Hoài", "Minh"):
            app = ChatWindow()
            app.root.withdraw()
            app.root.report_callback_exception = lambda *args: self.errors.append(args)
            app.username = app.display_name = name
            app.profile = LocalProfile(name, name, "SV", app.tcp.start(0))
            app.profile_frame.destroy()
            app._build_chat_view()
            app.chat_network = ChatSessionService(app.profile, app.tcp, app.post_network_event)
            app.chat_network.start()
            app._drain_network_events()
            self.apps.append(app)
        for app in self.apps:
            peers = {other.username: ChatSessionTests.peer(other.chat_network)
                     for other in self.apps if other is not app}
            discovery = unittest.mock.Mock()
            discovery.get_peer.side_effect = peers.get
            discovery.list_peers.side_effect = lambda p=peers: list(p.values())
            app.discovery = discovery
            app._refresh_online_peers()

    def tearDown(self) -> None:
        """Đóng mọi Tk root và xác nhận callback không phát sinh lỗi."""
        for app in self.apps:
            if app.root.winfo_exists():
                app._on_close()
        self.assertEqual(self.errors, [])

    def wait(self, predicate, timeout: float = 3) -> None:
        """Bơm event loop Tk trên luồng chính cho tới khi điều kiện đúng."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for app in self.apps:
                app.root.update()
            if predicate():
                return
            time.sleep(0.01)
        self.assertTrue(predicate(), "UI không đạt trạng thái mong đợi")

    def test_invite_accept_send_unread_drafts_and_decline(self) -> None:
        """Kiểm tra đủ luồng người dùng, giữ cuộc chat đang mở và nội dung gõ."""
        a, b, c = self.apps
        b.notifications_var.set(False)
        b._show_conversation(c.username)
        a._show_conversation(b.username)
        self.assertTrue(a.invite_button.winfo_manager())
        self.assertEqual(str(a.message_entry["state"]), "disabled")
        a.invite_button.invoke()
        self.wait(lambda: b._chat_states.get(a.username) == "incoming")
        self.assertEqual(b.current_chat, c.username)
        self.assertTrue(any("Lời mời" in row for row in b.conversation_list.get(0, "end")))
        b._show_conversation(a.username)
        self.assertTrue(b.accept_button.winfo_manager())
        b.accept_button.invoke()
        self.wait(lambda: a._chat_states.get(b.username) == b._chat_states.get(a.username) == "ready")
        self.assertEqual(str(a.message_entry["state"]), "normal")
        self.assertEqual(str(b.send_button["state"]), "normal")
        self.assertFalse(b.invitation_frame.winfo_manager())

        a.message_var.set("Xin chào Hoài 👋")
        a.send_button.invoke()
        self.wait(lambda: len(b.chat_history[a.username]) == len(a.chat_history[b.username]) == 1)
        self.assertEqual(b.chat_history[a.username][0][1], "Xin chào Hoài 👋")
        self.assertEqual(a.chat_history[b.username][0][0], "Bạn")
        b.message_var.set("Nội dung đang gõ")
        b._show_conversation(c.username)
        a.message_var.set("Tin tới khi bạn đang mở Minh")
        a._on_send()
        self.wait(lambda: b.unread_count[a.username] == 1)
        self.assertEqual(b.current_chat, c.username)
        b._show_conversation(a.username)
        self.assertEqual(b.unread_count[a.username], 0)
        self.assertEqual(b.message_var.get(), "Nội dung đang gõ")
        b._on_send()
        self.wait(lambda: any(text == "Nội dung đang gõ" for _, text in a.chat_history[b.username]))

        # Mất presence không tự đóng một kết nối TCP vẫn đang hoạt động.
        b._peer_info[a.username]["status"] = "offline"
        b._update_chat_controls()
        self.assertEqual(str(b.send_button["state"]), "normal")

        c._show_conversation(b.username)
        c.invite_button.invoke()
        self.wait(lambda: b._chat_states.get(c.username) == "incoming")
        b._show_conversation(c.username)
        b.decline_button.invoke()
        self.wait(lambda: c._chat_states.get(b.username) == "declined")
        self.assertEqual(str(c.send_button["state"]), "disabled")
        self.assertTrue(b.chat_history[a.username])

    def test_send_failure_restores_composer(self) -> None:
        """Gửi lỗi trả lại nội dung cho đúng hội thoại thay vì làm mất tin."""
        a, b, _ = self.apps
        a._show_conversation(b.username)
        a.invite_button.invoke()
        self.wait(lambda: b._chat_states.get(a.username) == "incoming")
        b._show_conversation(a.username)
        b.accept_button.invoke()
        self.wait(lambda: a._chat_states.get(b.username) == b._chat_states.get(a.username) == "ready")

        def fail_send(connection: socket.socket, text: str) -> None:
            """Mô phỏng đường TCP bị lỗi khi người dùng bấm Gửi."""
            raise OSError("Lỗi gửi thử nghiệm")

        with patch("network.tcp.chat_session.send_message", fail_send):
            a.message_var.set("Tin nhắn không được mất")
            a.send_button.invoke()
            self.wait(lambda: a.message_var.get() == "Tin nhắn không được mất")
            self.assertIn("Chưa gửi được tin", a.connection_notice_var.get())
            self.assertEqual(a.chat_history[b.username], [])


if __name__ == "__main__":
    unittest.main()
