"""Kiểm thử lời mời và UI bằng socket TCP thật trên loopback."""

import gc
import queue
import socket
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from models.peer import LocalProfile, Peer
from network.tcp.chat_session import ChatSessionService, PROTOCOL
from network.tcp.framing import HEADER, encode_frame, recv_frame, send_frame
from network.tcp.tcp_service import TCPChatService
from ui.app import ChatWindow


class ChatSessionTests(unittest.TestCase):
    """Kiểm tra giao thức, cạnh tranh kết nối và thu hồi worker/socket."""

    def setUp(self) -> None:
        """Mở hai listener riêng; ghi sự kiện mà không sử dụng Tk."""
        self.services = []
        self.downloads = Path(self.enterContext(TemporaryDirectory()))
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
            profile, listener, lambda *event: events.put(event), downloads=self.downloads / username, **options,
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

    def test_terminal_send_offers_file_before_transferring_bytes(self) -> None:
        """Lệnh /send qua phiên thật chỉ thông báo tên, kích thước, hash và mã lần gửi."""
        import hashlib
        import uuid
        import main as cli

        self.accept_pair(self.a, self.b)
        with TemporaryDirectory() as folder:
            path = Path(folder, "báo cáo.txt")
            content = "Nội dung riêng của file".encode("utf-8")
            path.write_bytes(content)
            from unittest.mock import Mock
            discovery = Mock()
            discovery.get_peer.return_value = self.peer(self.b)

            def commands():
                """Chọn b, gửi file rồi chờ b nhận và trả lời trước khi rời chat."""
                yield "/chat b"
                yield f'/send "{path}"'
                received.append(self.wait_event("b", "file_offer"))
                self.b.send_text("a", "Vẫn đang chat")
                self.assertEqual(self.wait_event("a", "message")[2]["text"], "Vẫn đang chat")
                yield "/leave"
                yield "/quit"

            received = []
            with patch("builtins.input", side_effect=commands()), patch("builtins.print"):
                cli.run_console(discovery, self.a)
            _, sender, offer = received[0]
            self.assertEqual(sender, "a")
            self.assertEqual(set(offer), {"transfer_id", "name", "size", "sha256"})
            self.assertEqual(uuid.UUID(hex=offer["transfer_id"]).hex, offer["transfer_id"])
            self.assertEqual(offer["name"], path.name)
            self.assertEqual(offer["size"], len(content))
            self.assertEqual(offer["sha256"], hashlib.sha256(content).hexdigest())

    def test_terminal_three_peers_switch_unread_and_disconnect(self) -> None:
        """Callback TCP thật lưu tin nền, chuyển phiên cũ và trả prompt khi đóng."""
        import io
        from contextlib import redirect_stdout
        from unittest.mock import Mock
        from console_state import ConsoleState
        from main import run_console, show_chat_event

        c = self.make_service("c")
        state = ConsoleState(show_chat_event)

        def emit(*event):
            """Giữ hàng sự kiện của test đồng thời cập nhật terminal."""
            state.on_event(*event)
            self.events["a"].put(event)

        self.a.emit = emit
        discovery = Mock()
        with redirect_stdout(io.StringIO()) as output:
            self.accept_pair(self.a, self.b)
            self.accept_pair(self.a, c)
            original_b = self.a._links["b"]
            original_c = self.a._links["c"]

            def commands():
                """Phát tin qua socket giữa các lần nhập lệnh."""
                yield "/chat b"
                c.send_text("a", "tin nền 1")
                self.wait_event("a", "message")
                c.send_text("a", "tin nền 2")
                self.wait_event("a", "message")
                yield "/chats"
                yield "/chat c"
                self.assertIs(self.a._links["b"], original_b)
                self.assertIs(self.a._links["c"], original_c)
                yield "đã nhận đủ"
                self.assertEqual(self.wait_event("c", "message")[2]["text"], "đã nhận đủ")
                c.leave_chat("a")
                self.wait(lambda: state.current == "")
                yield "/chats"
                yield "/quit"

            with patch("builtins.input", side_effect=commands()):
                run_console(discovery, self.a, state)
        discovery.get_peer.assert_not_called()
        self.assertIn("c | ready | 2 tin chưa đọc", output.getvalue())
        self.assertIn("c: tin nền 1", output.getvalue())
        self.assertIn("c: tin nền 2", output.getvalue())
        self.assertIn("c | disconnected | 0 tin chưa đọc", output.getvalue())
        self.assertEqual(state.prompt(), "> ")

    def test_file_reply_matches_pending_offer(self) -> None:
        """Hai lời mời cùng tên được trả lời ngược thứ tự, mỗi mã chỉ dùng một lần."""
        self.accept_pair(self.a, self.b)
        with TemporaryDirectory() as folder:
            path = Path(folder, "báo cáo.txt")
            path.write_bytes(b"abc")
            ids = []
            for _ in range(2):
                self.a.offer_file("b", path)
                ids.append(self.wait_event("b", "file_offer")[2]["transfer_id"])
            self.assertNotEqual(*ids)
            for transfer_id, accepted in ((ids[1], False), (ids[0], True)):
                self.b.reply_file("a", transfer_id, accepted)
                _, peer, reply = self.wait_event("a", "file_reply")
                self.assertEqual((peer, reply["transfer_id"], reply["name"], reply["accepted"]),
                                 ("b", transfer_id, path.name, accepted))
                with self.assertRaises(ValueError):
                    self.b.reply_file("a", transfer_id, accepted)
            self.b.send_text("a", "Vẫn đang chat")
            self.assertEqual(self.wait_event("a", "message")[2]["text"], "Vẫn đang chat")

    def test_transfer_while_chatting(self) -> None:
        """Dừng giữa hai khối dữ liệu để xác nhận chat và ACK vẫn hoạt động."""
        from network.tcp.file_transfer import send_file_bytes
        self.accept_pair(self.a, self.b)
        resume = threading.Event()
        data = bytes(range(256)) * 700
        path = self.downloads / "ảnh thử.bin"
        path.write_bytes(data)
        (self.downloads / "b").mkdir()
        existing = self.downloads / "b" / path.name
        existing.write_bytes(b"keep")

        def slow_send(conn, path, size, progress):
            def pause(count):
                progress(count)
                if count < size and not resume.wait(3):
                    raise TimeoutError("Worker gửi file chưa được tiếp tục")
            return send_file_bytes(conn, path, size, pause)

        self.a.offer_file("b", path)
        offer = self.wait_event("b", "file_offer")[2]
        with patch("network.tcp.chat_session.send_file_bytes", slow_send):
            self.b.reply_file("a", offer["transfer_id"], True)
            try:
                self.wait_event("b", "file_progress")
                self.b.send_text("a", "Chat giữa hai khối file")
                self.assertEqual(self.wait_event("a", "message")[2]["text"], "Chat giữa hai khối file")
                self.wait_event("b", "ack_received")
            finally:
                resume.set()
            saved = Path(self.wait_event("b", "file_received")[2]["path"])
            self.wait_event("a", "file_sent")
        self.assertEqual(saved.read_bytes(), data)
        self.assertEqual(existing.read_bytes(), b"keep")
        self.assertFalse(list(saved.parent.glob("*.part")))

    def test_transfer_changed_content(self) -> None:
        """File cùng kích thước nhưng khác hash được dọn sạch, phiên chat còn mở."""
        self.accept_pair(self.a, self.b)
        path = self.downloads / "changed.txt"
        path.write_bytes(b"abc")
        self.a.offer_file("b", path)
        offer = self.wait_event("b", "file_offer")[2]
        path.write_bytes(b"xyz")
        self.b.reply_file("a", offer["transfer_id"], True)
        self.assertIn("SHA-256", self.wait_event("b", "file_error")[2]["reason"])
        self.wait_event("a", "file_error")
        self.assertEqual(list(self.b.downloads.iterdir()), [])
        self.assertEqual(self.state(self.a, "b"), "ready")

    def test_same_text_has_distinct_message_ids(self) -> None:
        """Hai tin cùng nội dung trong một phiên phải có hai UUID riêng."""
        import uuid

        self.accept_pair(self.a, self.b)
        with patch("network.tcp.chat_session.send_frame", wraps=send_frame) as writer:
            for _ in range(2):
                self.a.send_text("b", "OK")
                self.assertEqual(self.wait_event("b", "message")[2]["text"], "OK")

        messages = [
            call.args[1] for call in writer.call_args_list
            if call.args[1]["type"] == "message"
        ]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["request_id"], messages[1]["request_id"])
        for packet in messages:
            self.assertIn("message_id", packet)
        first_id, second_id = (uuid.UUID(hex=p["message_id"]) for p in messages)
        self.assertNotEqual(first_id, second_id)

    def test_ack_returns_original_message_id(self) -> None:
        """ACK về đúng bên gửi và mang mã của từng tin đã tiếp nhận."""
        self.accept_pair(self.a, self.b)
        with patch("network.tcp.chat_session.send_frame", wraps=send_frame) as writer:
            for _ in range(2):
                self.a.send_text("b", "OK")
                self.assertEqual(self.wait_event("b", "message")[2]["text"], "OK")
                sender, payload = self.wait_event("a", "ack_received")[1:]
                sent = [call.args[1] for call in writer.call_args_list
                        if call.args[1]["type"] == "message"]
                self.assertEqual(sender, "b")
                self.assertEqual(payload["message_id"], sent[-1]["message_id"])

    def test_duplicate_and_unknown_ack_are_ignored(self) -> None:
        """Mỗi tin gửi chỉ được xác nhận một lần trong đúng phiên."""
        import uuid

        self.accept_pair(self.a, self.b)
        self.a.send_text("b", "OK")
        _, _, ack = self.wait_event("a", "ack_received")
        link = self.a._links["b"]

        with patch.object(self.a, "emit", wraps=self.a.emit) as emit:
            for message_id in (ack["message_id"], uuid.uuid4().hex):
                self.a._handle_packet(link, {
                    "protocol": PROTOCOL,
                    "request_id": link.request_id,
                    "type": "ack",
                    "message_id": message_id,
                })
            self.assertFalse(any(call.args[0] == "ack_received"
                                 for call in emit.call_args_list))
        self.assertEqual(self.state(self.a, "b"), "ready")

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

        def fail_message(connection: socket.socket, packet: dict) -> None:
            """Gây lỗi riêng ở tin chat, giữ nguyên các gói điều khiển."""
            if packet["type"] == "message":
                raise OSError("Lỗi gửi dùng trong test")
            send_frame(connection, packet)

        with patch("network.tcp.chat_session.send_frame", fail_message):
            self.a.send_text("b", "Nội dung cần giữ")
            event = self.wait_event("a", "send_failed")
            self.assertEqual(event[2]["text"], "Nội dung cần giữ")
            self.wait(lambda: self.state(self.a, "b") == self.state(self.b, "a") == "closed")

    def test_completed_send_is_recorded_even_if_eof_arrives_first(self) -> None:
        """EOF ngay sau sendall không làm biến mất tin đã gửi khỏi lịch sử local."""
        self.accept_pair(self.a, self.b)
        link = self.a._links["b"]

        def send_then_disconnect(connection: socket.socket, packet: dict) -> None:
            """Cho reader kết thúc trước khi writer kịp phát sự kiện sent."""
            send_frame(connection, packet)
            if packet["type"] == "message":
                self.a._drop(link, "EOF mô phỏng ngay sau gửi")

        with patch("network.tcp.chat_session.send_frame", send_then_disconnect):
            self.a.send_text("b", "Tin vừa gửi")
            self.assertEqual(self.wait_event("a", "sent")[2]["text"], "Tin vừa gửi")

    def test_malformed_connection_does_not_stop_listener(self) -> None:
        """Dữ liệu sai chỉ đóng socket lỗi; listener còn nhận lời mời mới."""
        with socket.create_connection(("127.0.0.1", self.b.profile.tcp_port)) as raw:
            raw.settimeout(2)
            raw.sendall(HEADER.pack(255, 0))
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
            data = encode_frame(packet)
            for start in range(0, len(data), 3):
                raw.sendall(data[start:start + 3])
            self.wait(lambda: self.state(self.b, "raw") == "incoming")
            self.b.accept_chat("raw")
            self.assertEqual(recv_frame(raw)["type"], "accept")
            messages = [dict(protocol=PROTOCOL, request_id=request_id,
                             type="message", message_id=uuid.uuid4().hex,
                             text=f"Tin {i} 👋") for i in range(3)]
            raw.sendall(b"".join(encode_frame(p) for p in messages))
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
        while self.apps:
            app = self.apps.pop()
            if app.root.winfo_exists():
                app._on_close()
            del app
        # Thu hồi cả các đối tượng Tk có tham chiếu vòng ngay trên luồng UI.
        gc.collect()
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
        self.wait(lambda: "Đã nhận" in a.history_text.get("1.0", "end-1c"))
        self.assertNotIn("Đã nhận", b.history_text.get("1.0", "end-1c"))
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

    def test_choose_file_for_ready_conversation(self) -> None:
        """Chọn file cho đúng peer, giữ bản đã chọn khi hủy hoặc chọn file lỗi."""
        a, b, c = self.apps
        a._show_conversation(b.username)
        self.assertTrue(a.file_button.instate(["disabled"]))
        a.invite_button.invoke()
        self.wait(lambda: b._chat_states.get(a.username) == "incoming")
        b._show_conversation(a.username)
        b.accept_button.invoke()
        self.wait(lambda: a._chat_states.get(b.username) == "ready")
        self.assertFalse(a.file_button.instate(["disabled"]))

        with TemporaryDirectory() as folder:
            selected = Path(folder, "ghi chú.txt")
            selected.write_bytes(b"hello")
            oversized = Path(folder, "qua-lon.bin")
            with oversized.open("wb") as stream:
                stream.truncate(100 * 1024 * 1024 + 1)
            choices = [str(selected), "", str(oversized), str(selected.with_suffix(".missing"))]
            with patch("tkinter.filedialog.askopenfilename", side_effect=choices):
                a.file_button.invoke()
                self.assertIn(selected.name, a.connection_notice_var.get())
                self.assertIn("5 byte", a.connection_notice_var.get())
                for _ in choices[1:]:
                    a.file_button.invoke()
                    self.assertEqual(a._file_drafts[b.username], selected)
        a._show_conversation(c.username)
        self.assertTrue(a.file_button.instate(["disabled"]))
        self.assertNotIn(c.username, a._file_drafts)
        self.assertEqual(b.chat_history[a.username], [])

    def test_ui_send_accept_and_decline_files(self) -> None:
        """Hai cửa sổ chọn, từ chối rồi nhận file thật sau khi chuyển hội thoại."""
        a, b, c = self.apps
        a._show_conversation(b.username)
        a.invite_button.invoke()
        self.wait(lambda: b._chat_states.get(a.username) == "incoming")
        b._show_conversation(a.username)
        b.accept_button.invoke()
        self.wait(lambda: a._chat_states.get(b.username) == "ready")
        b._show_conversation(c.username)
        with TemporaryDirectory() as folder:
            b.chat_network.downloads = Path(folder, "downloads")
            path = Path(folder, "ảnh thử.bin")
            path.write_bytes(bytes(range(256)) * 1500)
            with patch("tkinter.filedialog.askopenfilename", return_value=str(path)):
                for _ in range(2):
                    a.file_button.invoke()
                    a.send_file_button.invoke()
            self.wait(lambda: len(b._file_offers.get(a.username, {})) == 2)
            self.assertEqual(b.current_chat, c.username)
            self.assertTrue(any("2 file chờ nhận" in s for s in b.conversation_list.get(0, "end")))
            b._show_conversation(a.username)
            b.message_var.set("Mình đang đọc")
            b.decline_button.invoke()
            b.accept_button.invoke()
            self.wait(lambda: "100%" in b.history_text.get("1.0", "end"))
            self.wait(lambda: "100%" in a.history_text.get("1.0", "end"))
            self.assertIn("Đã từ chối", a.history_text.get("1.0", "end"))
            self.assertEqual(list(b.chat_network.downloads.iterdir()), [b.chat_network.downloads / path.name])
            self.assertEqual((b.chat_network.downloads / path.name).read_bytes(), path.read_bytes())
            self.assertEqual(b.message_var.get(), "Mình đang đọc")
            b.send_button.invoke()
            self.wait(lambda: "Mình đang đọc" in a.history_text.get("1.0", "end"))

    def test_ack_ui_matches_identical_messages_after_switch(self) -> None:
        """ACK đến sớm hoặc muộn đều đánh dấu đúng tin sau khi đổi cuộc chat."""
        a, b, c = self.apps
        a._show_conversation(c.username)
        first, second = "1" * 32, "2" * 32
        a.post_network_event("ack_received", b.username, {"message_id": second})
        for message_id in (first, second):
            a.post_network_event("sent", b.username, {"message_id": message_id, "text": "OK"})
        self.wait(lambda: len(a.chat_history.get(b.username, [])) == 2)
        self.assertEqual(a.current_chat, c.username)
        self.assertNotIn("Đã nhận", a.history_text.get("1.0", "end-1c"))

        a._show_conversation(b.username)
        _, first_row, second_row = a.history_text.get("1.0", "end-1c").split("OK")
        self.assertNotIn("Đã nhận", first_row)
        self.assertIn("Đã nhận", second_row)

        a.post_network_event("ack_received", b.username, {"message_id": first})
        self.wait(lambda: a.history_text.get("1.0", "end-1c").count("Đã nhận") == 2)
        self.assertEqual(len(a.chat_history[b.username]), 2)

    def test_leave_closes_only_current_chat_and_allows_reinvite(self) -> None:
        """/leave đóng phiên đang chọn và cho phép mời lại."""
        a, b, c = self.apps

        def open_chat(sender: ChatWindow, recipient: ChatWindow) -> None:
            """Mở hội thoại qua các nút thật của UI và chờ hai đầu ready."""
            sender._show_conversation(recipient.username)
            sender.invite_button.invoke()
            self.wait(lambda: recipient._chat_states.get(sender.username) == "incoming")
            recipient._show_conversation(sender.username)
            recipient.accept_button.invoke()
            self.wait(lambda: sender._chat_states.get(recipient.username)
                      == recipient._chat_states.get(sender.username) == "ready")

        open_chat(a, b)
        a.message_var.set("Tin nhắn trước khi rời chat")
        a.send_button.invoke()
        self.wait(lambda: len(a.chat_history[b.username])
                  == len(b.chat_history[a.username]) == 1)
        history_a = list(a.chat_history[b.username])
        history_b = list(b.chat_history[a.username])
        socket_a = a.chat_network._links[b.username].connection
        socket_b = b.chat_network._links[a.username].connection
        open_chat(a, c)

        a._show_conversation(b.username)
        a.message_var.set("/leave")
        a.send_button.invoke()
        self.wait(lambda: a._chat_states.get(b.username)
                  == b._chat_states.get(a.username) == "disconnected")
        self.assertEqual(socket_a.fileno(), -1)
        self.assertEqual(socket_b.fileno(), -1)
        self.assertEqual(a.message_var.get(), "")
        self.assertEqual(a.chat_history[b.username], history_a)
        self.assertEqual(b.chat_history[a.username], history_b)
        self.assertEqual(str(a.message_entry["state"]), "disabled")
        self.assertTrue(a.invite_button.winfo_manager())
        self.assertEqual(a.root.winfo_exists(), 1)
        self.assertIsNotNone(a.tcp._listener)
        a.discovery.stop.assert_not_called()

        # Phiên khác vẫn chat được sau khi rời cuộc chat với Hoài.
        a._show_conversation(c.username)
        a.message_var.set("Vẫn chat với Minh")
        a.send_button.invoke()
        self.wait(lambda: bool(c.chat_history[a.username]))
        self.assertEqual(c.chat_history[a.username][-1][1], "Vẫn chat với Minh")

        # Có thể mời lại và dùng /leave qua handler của phím Enter.
        open_chat(a, b)
        a.message_var.set("  /leave  ")
        self.assertEqual(a._on_send(), "break")
        self.wait(lambda: a._chat_states.get(b.username)
                  == b._chat_states.get(a.username) == "disconnected")
        self.assertEqual(a.chat_history[b.username], history_a)
        self.assertEqual(b.chat_history[a.username], history_b)

    def test_send_failure_restores_composer(self) -> None:
        """Gửi lỗi trả lại nội dung cho đúng hội thoại thay vì làm mất tin."""
        a, b, _ = self.apps
        a._show_conversation(b.username)
        a.invite_button.invoke()
        self.wait(lambda: b._chat_states.get(a.username) == "incoming")
        b._show_conversation(a.username)
        b.accept_button.invoke()
        self.wait(lambda: a._chat_states.get(b.username) == b._chat_states.get(a.username) == "ready")

        def fail_send(connection: socket.socket, packet: dict) -> None:
            """Mô phỏng đường TCP bị lỗi khi người dùng bấm Gửi."""
            raise OSError("Lỗi gửi thử nghiệm")

        with patch("network.tcp.chat_session.send_frame", fail_send):
            a.message_var.set("Tin nhắn không được mất")
            a.send_button.invoke()
            self.wait(lambda: a.message_var.get() == "Tin nhắn không được mất")
            self.assertIn("Chưa gửi được tin", a.connection_notice_var.get())
            self.assertEqual(a.chat_history[b.username], [])


if __name__ == "__main__":
    unittest.main()
