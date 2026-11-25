import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from config import DEFAULT_STATUS, PORT_DEFAULT, MAX_FILE_BYTES
from models.peer import LocalProfile
from network.tcp.chat_session import ChatSessionService
from network.tcp.tcp_service import TCPChatService
from network.udp.discovery_service import DiscoveryService
from ui.chat_layout import build_footer, build_header
from ui.conversation_view import (
    build_attachment, build_composer, build_conversation, build_history, build_invitation, render_history,
)
from ui.message_history import MessageHistory
from ui.network_events import NetworkEventQueue
from ui.peer_directory import PeerDirectory
from ui.profile_view import build_profile_form
from ui.sidebar import build_sidebar, replace_rows
from ui.styles import configure_styles


class ChatWindow:
    """Điều phối màn hình Tkinter, thao tác người dùng và các dịch vụ LAN Chat."""

    def __init__(self) -> None:
        """Khởi tạo cửa sổ chính, biến trạng thái, style giao diện và hiển thị form hồ sơ."""
        self.root = tk.Tk()
        self.root.title("LAN Chat P2P • HCMUS")
        self.root.geometry("500x420")
        self.root.resizable(True, True)

        # Cấu hình màu nền ứng dụng hiện đại (Slate 50)
        self.root.configure(bg="#f8fafc")

        # Khởi tạo các biến ràng buộc dữ liệu (Tkinter variables)
        self.username_var = tk.StringVar(self.root)
        self.display_name_var = tk.StringVar(self.root)
        self.job_title_var = tk.StringVar(self.root)
        self.notice_var = tk.StringVar(self.root)
        self.notifications_var = tk.BooleanVar(self.root, value=True)

        self.username: str = ""
        self.display_name: str = ""
        self.job_title: str = "Nhân viên"

        # Các dịch vụ mạng nền tảng
        self.tcp = TCPChatService()
        self.discovery: DiscoveryService | None = None
        self.profile: LocalProfile | None = None
        self._poll_id: str | None = None

        self.chat_network: ChatSessionService | None = None
        self._events = NetworkEventQueue()
        self._events_poll_id: str | None = None

        # Thiết lập bảng màu và phong cách hiện đại cho ttk widget
        self.style = configure_styles(self.root)

        # Bắt sự kiện người dùng đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        menu_bar = tk.Menu(self.root)
        app_menu = tk.Menu(menu_bar, tearoff=False)
        app_menu.add_command(
            label="Thoát",
            accelerator="Ctrl+Q",
            command=self._on_close,
        )
        menu_bar.add_cascade(label="Ứng dụng", menu=app_menu)
        self.root.configure(menu=menu_bar)

        self.root.bind("<Control-q>", lambda event: self._on_close())

        # Khởi dựng màn hình đăng nhập hồ sơ ban đầu
        self._build_profile_form()

    def _build_profile_form(self) -> None:
        """Hiển thị form nhập hồ sơ và liên kết nút bắt đầu."""
        self.profile_frame = build_profile_form(
            self.root, self.username_var, self.display_name_var,
            self.job_title_var, self.notice_var, self._on_start,
        )

    def _on_start(self) -> None:
        """Xác thực thông tin hồ sơ, khởi động mạng TCP/UDP và mở màn hình chat chính."""
        username = self.username_var.get().strip()

        if not username:
            self.notice_var.set("Vui lòng nhập username để tiếp tục.")
            return

        self.username = username
        self.display_name = (
            self.display_name_var.get().strip() or username
        )
        self.job_title = (
            self.job_title_var.get().strip() or "Nhân viên"
        )

        try:
            # Khởi động TCP listener trên cổng mặc định (hoặc cấp động nếu bận)
            actual_port = self.tcp.start(PORT_DEFAULT)

            self.profile = LocalProfile(
                username=self.username,
                display_name=self.display_name,
                job_title=self.job_title,
                tcp_port=actual_port,
                status=DEFAULT_STATUS,
            )

            # Khởi động dịch vụ khám phá UDP và dịch vụ quản lý phiên TCP
            self.discovery = DiscoveryService(self.profile)
            self.discovery.start()
            self.chat_network = ChatSessionService(
                self.profile, self.tcp, self.post_network_event,
            )
            self.chat_network.start()

        except (OSError, ValueError, RuntimeError) as error:
            if self.chat_network is not None:
                self.chat_network.stop()
                self.chat_network = None
            if self.discovery is not None:
                self.discovery.stop()
                self.discovery = None

            self.tcp.stop()
            self.notice_var.set(f"Không thể khởi động mạng: {error}")
            return

        # Hủy giao diện đăng nhập và chuyển sang giao diện chat chính
        self.profile_frame.destroy()
        self._build_chat_view()
        self._refresh_online_peers()
        self._drain_network_events()

    def _on_close(self) -> None:
        """Dọn dẹp tài nguyên hẹn giờ (timer), dừng mọi dịch vụ mạng và hủy cửa sổ."""
        self._events.close()

        for name in ("_poll_id", "_events_poll_id"):
            timer_id = getattr(self, name)
            if timer_id is not None:
                self.root.after_cancel(timer_id)
                setattr(self, name, None)

        try:
            if self.chat_network is not None:
                self.chat_network.stop()
                self.chat_network = None
            if self.discovery is not None:
                self.discovery.stop()
                self.discovery = None
        finally:
            self.tcp.stop()
            self.root.destroy()

    def _build_chat_view(self) -> None:
        """Ghép các phần của màn hình chat và kết nối thao tác với controller."""
        self.root.geometry("980x640")
        self.root.minsize(780, 500)
        self.chat_frame = ttk.Frame(self.root, padding=0)
        self.chat_frame.pack(fill="both", expand=True)
        self.chat_frame.columnconfigure(1, weight=1)
        self.chat_frame.rowconfigure(1, weight=1)

        self.status_var, self.status_box, self.notifications_toggle = build_header(
            self.chat_frame,
            username=self.username or (self.profile.username if self.profile else ""),
            display_name=self.display_name or (self.profile.display_name if self.profile else self.username),
            job_title=self.job_title or (self.profile.job_title if self.profile else "Nhân viên"),
            status=self.profile.status if self.profile else DEFAULT_STATUS,
            notifications_var=self.notifications_var,
            on_status_changed=self._on_status_changed,
            on_notifications_toggled=self._on_notifications_toggled,
        )
        self.peer_list, self.conversation_list, self.reload_peers_button = build_sidebar(
            self.chat_frame, lambda: self._refresh_online_peers(force=True, schedule_next=False),
        )
        panel, self.chat_title_var = build_conversation(self.chat_frame)
        (self.invitation_frame, self.invitation_var, self.invite_button,
         self.accept_button, self.decline_button) = build_invitation(
            panel, self._on_invite, self._on_accept_chat, self._on_decline_chat,
        )
        self.history_text = build_history(panel)
        self.message_var, self.message_entry, self.send_button, self.file_button = build_composer(
            panel, self._on_send,
        )
        self.connection_notice_var = build_footer(self.chat_frame)
        self.file_button.configure(command=self._choose_file)
        self.attachment_row, self.attachment_name, self.send_file_button = build_attachment(
            panel, self._send_file, self._remove_file,
        )
        self._init_chat_data()
        self._update_chat_controls()
        self.peer_list.bind("<<ListboxSelect>>", self._on_chat_selected)
        self.conversation_list.bind("<<ListboxSelect>>", self._on_chat_selected)

    def _init_chat_data(self) -> None:
        """Tạo kho lưu trữ hội thoại trống; danh sách peer sẽ nhận từ UDP."""
        self.current_chat: str | None = None

        self._peers = PeerDirectory()
        self._conversation_order: list[str] = []

        self._history = MessageHistory()
        self.unread_count: dict[str, int] = {}
        self._chat_states: dict[str, str] = {}
        self._chat_reasons: dict[str, str] = {}
        self._drafts: dict[str, str] = {}
        self._file_drafts: dict[str, Path] = {}
        self._file_offers: dict[str, dict[str, dict]] = {}

        self.peer_list.delete(0, tk.END)
        self.conversation_list.delete(0, tk.END)

    @property
    def _peer_info(self) -> dict[str, dict]:
        """Thông tin peer dùng khi hiển thị hội thoại."""
        return self._peers.info

    @property
    def _peer_order(self) -> list[str]:
        """Thứ tự username tương ứng với các dòng danh sách online."""
        return self._peers.online

    @property
    def chat_history(self) -> dict[str, list[tuple[str, str]]]:
        """Lịch sử các hội thoại theo username."""
        return self._history.messages

    def _on_chat_selected(self, event: tk.Event) -> None:
        """Nhận sự kiện chọn từ danh sách peer hoặc conversation và mở cuộc chat."""
        source = event.widget
        selected = source.curselection()

        if not selected:
            return

        index = selected[0]

        if source is self.peer_list:
            username = self._peer_order[index]
            self.conversation_list.selection_clear(0, tk.END)
        else:
            username = self._conversation_order[index]
            self.peer_list.selection_clear(0, tk.END)

        self._show_conversation(username)

    def _show_conversation(self, username: str) -> None:
        """Mở cuộc chat với username được chọn; lưu bản nháp và hiển thị lịch sử."""
        if self.current_chat is not None:
            self._drafts[self.current_chat] = self.message_var.get()
        self.current_chat = username
        self.message_var.set(self._drafts.get(username, ""))
        peer = self._peer_info[username]

        if username not in self._conversation_order:
            self._conversation_order.append(username)

        self.chat_title_var.set(
            f"{peer['display_name']} · {peer['status']}"
        )

        self._render_history()

        self.unread_count[username] = 0
        self._refresh_conversation_list()
        self._update_chat_controls()

    def _render_history(self) -> None:
        """Vẽ lịch sử của người đang được chọn."""
        render_history(self.history_text, self._history, self.current_chat)

    def _receive_message(
        self,
        username: str,
        text: str,
    ) -> None:
        """Lưu tin nhắn nhận được vào lịch sử và tăng bộ đếm chưa đọc nếu chưa mở hội thoại."""
        if not text.strip():
            return

        peer = self._peers.remember(username, {})
        self._history.received(username, peer["display_name"], text)
        self.unread_count.setdefault(username, 0)

        if username not in self._conversation_order:
            self._conversation_order.append(username)

        if username == self.current_chat:
            self._render_history()
        else:
            self.unread_count[username] += 1

        self._refresh_conversation_list()
        self.connection_notice_var.set(
            f"Tin mới từ {peer['display_name']}."
        )

    def _refresh_conversation_list(self) -> None:
        """Cập nhật nhãn và số tin chưa đọc trong danh sách hội thoại gần đây."""
        selected = self.conversation_list.curselection()
        labels = []

        for username in self._conversation_order:
            name = self._peer_info[username]["display_name"]
            count = self.unread_count[username]

            label = f"{name} ({count})" if count else name
            offers = self._file_offers.get(username)
            if offers:
                label += f" · {len(offers)} file chờ nhận"
            state = self._chat_states.get(username)
            if state == "incoming":
                label += " · Lời mời"
            elif state in ("connecting", "waiting", "accepting"):
                label += " · Đang chờ"
            labels.append(label)

        replace_rows(self.conversation_list, labels, selected[0] if selected else None)

    def _refresh_online_peers(
        self,
        *,
        force: bool = False,
        schedule_next: bool = True,
    ) -> None:
        """Đồng bộ danh sách người dùng online từ UDP DiscoveryService."""
        if self.discovery is None:
            return

        peers = sorted(
            self.discovery.list_peers(),
            key=lambda peer: peer.username,
        )

        previous_order = self._peer_order
        presence_notice = self._peers.refresh(
            peers, force=force, notify=self.notifications_var.get(),
        )
        if presence_notice is not None:
            selected = self.peer_list.curselection()
            selected_username = previous_order[selected[0]] if selected else None
            for peer in peers:
                self.chat_history.setdefault(peer.username, [])
                self.unread_count.setdefault(peer.username, 0)

            labels = [f"{p.display_name} ({p.username}) · {p.status}" for p in peers]
            index = (
                self._peer_order.index(selected_username)
                if selected_username in self._peer_order else None
            )
            replace_rows(self.peer_list, labels, index)

            self._refresh_conversation_list()

            if self.current_chat is not None:
                info = self._peer_info[self.current_chat]
                self.chat_title_var.set(
                    f"{info['display_name']} · {info['status']}"
                )

            if presence_notice:
                self.connection_notice_var.set(presence_notice)
            else:
                self._show_network_summary()

            self._update_chat_controls()

        if schedule_next:
            self._poll_id = self.root.after(
                500,
                self._refresh_online_peers,
            )

    def _on_status_changed(
        self,
        event: tk.Event | None = None,
    ) -> None:
        """Cập nhật trạng thái online hoặc away thông qua DiscoveryService."""
        if self.discovery is None or self.profile is None:
            return

        new_status = self.status_var.get()
        try:
            self.discovery.set_status(new_status)
        except ValueError:
            self.status_var.set(self.profile.status)
            self.connection_notice_var.set(
                "Trạng thái chỉ được là online hoặc away."
            )
            return

        self.connection_notice_var.set(
            f"Đã đặt trạng thái: {new_status}. Sẽ phát trong gói UDP tiếp theo."
        )

    def _show_network_summary(self) -> None:
        """Hiển thị tóm tắt tình trạng cổng TCP và số lượng peer hiện diện."""
        if self.profile is None:
            return

        self.connection_notice_var.set(
            f"UDP đang chạy · TCP port: {self.profile.tcp_port}"
            f" · {len(self._peer_order)} peer hiện diện."
        )

    def _on_notifications_toggled(self) -> None:
        """Xử lý bật/tắt hiển thị thông báo thay đổi hiện diện người dùng."""
        self._show_network_summary()

    def post_network_event(self, event_type: str, username: str, data: dict | str = "") -> None:
        """Callback dành cho worker TCP, được xử lý ở lượt cập nhật giao diện kế tiếp."""
        self._events.post(event_type, username, data)

    def _remember_chat_peer(self, username: str, data: dict) -> None:
        """Lưu thông tin peer nhận từ kết nối TCP phòng khi lượt UDP chưa cập nhật."""
        self._peers.remember(username, data)
        self.chat_history.setdefault(username, [])
        self.unread_count.setdefault(username, 0)
        if username not in self._conversation_order:
            self._conversation_order.append(username)

    def _drain_network_events(self) -> None:
        """Rút các sự kiện từ hàng đợi mạng và cập nhật giao diện trên luồng Tkinter."""
        self._events_poll_id = None
        if self._events.closed.is_set():
            return

        refresh_files = False
        for event_type, username, data in self._events.poll():

            if event_type == "chat_state":
                self._remember_chat_peer(username, data)
                self._chat_states[username] = data["state"]
                self._chat_reasons[username] = data.get("reason", "")
                if data["state"] in ("disconnected", "expired", "declined", "error"):
                    self._file_offers.pop(username, None)
                    self._history.interrupt_files(username)
                    refresh_files |= username == self.current_chat
                if data["state"] == "incoming":
                    name = self._peer_info[username]["display_name"]
                    self.connection_notice_var.set(
                        f"{name} muốn trò chuyện. Chọn hội thoại để trả lời."
                    )
                self._refresh_conversation_list()
                self._update_chat_controls()

            elif event_type == "message":
                self._receive_message(username, data["text"])

            elif event_type.startswith("file_"):
                self._handle_file_event(event_type, username, data)
                refresh_files |= username == self.current_chat

            elif event_type == "sent":
                self._remember_chat_peer(username, data)
                self._history.sent(username, data["text"], data["message_id"])

                if self.current_chat == username:
                    self._render_history()
                self._refresh_conversation_list()

            elif event_type == "ack_received":
                self._history.acknowledge(username, data["message_id"])
                if self.current_chat == username:
                    self._render_history()

            elif event_type == "send_failed":
                text = data["text"]
                draft = (
                    self.message_var.get()
                    if self.current_chat == username
                    else self._drafts.get(username, "")
                )
                self._drafts[username] = " ".join(
                    part for part in (draft, text) if part
                )
                if self.current_chat == username:
                    self.message_var.set(self._drafts[username])
                self.connection_notice_var.set(
                    f"Chưa gửi được tin tới {username}; đã giữ lại nội dung. "
                    f"{data.get('reason', '')}"
                )

            elif event_type == "network_error":
                self.connection_notice_var.set(
                    f"Không thể nhận kết nối mới: {data['reason']}"
                )

        if refresh_files:
            self._render_history()
        self._events_poll_id = self.root.after(
            100,
            self._drain_network_events,
        )

    def _update_chat_controls(self) -> None:
        """Cập nhật hiển thị khung lời mời và trạng thái ô nhập tin tùy theo hội thoại."""
        username = self.current_chat
        state = self._chat_states.get(username, "idle")

        for button in (
            self.invite_button,
            self.accept_button,
            self.decline_button,
        ):
            button.pack_forget()

        ready = state == "ready"
        self.file_button.configure(state="normal" if ready else "disabled")
        draft = self._file_drafts.get(username)
        if ready and draft:
            self.attachment_name.set(draft.name)
            self.attachment_row.grid()
        else:
            self.attachment_row.grid_remove()
        self.message_entry.configure(state="normal" if ready else "disabled")
        self.send_button.configure(state="normal" if ready else "disabled")

        if ready:
            offers = self._file_offers.get(username)
            if offers:
                offer = next(iter(offers.values()))
                self.invitation_var.set(f"{username} muốn gửi {offer['name']} ({offer['size']:,} byte).")
                self.invitation_frame.grid()
                self.accept_button.configure(text="Nhận file", command=lambda: self._reply_file(True))
                self.decline_button.configure(text="Từ chối file", command=lambda: self._reply_file(False))
                self.accept_button.pack(side="left")
                self.decline_button.pack(side="left", padx=(8, 0))
                return
            self.invitation_frame.grid_remove()
            return

        self.invitation_frame.grid()

        if username is None:
            self.invitation_var.set(
                "Chọn một người trong danh sách để bắt đầu."
            )
            return

        info = self._peer_info[username]
        name = info["display_name"]

        if state == "incoming":
            self.accept_button.configure(text="Đồng ý", command=self._on_accept_chat)
            self.decline_button.configure(text="Từ chối", command=self._on_decline_chat)
            self.invitation_var.set(f"{name} muốn trò chuyện với bạn.")
            self.accept_button.pack(side="left")
            self.decline_button.pack(side="left", padx=(8, 0))
        elif state == "connecting":
            self.invitation_var.set(f"Đang gửi lời mời tới {name}…")
        elif state == "waiting":
            self.invitation_var.set(
                f"Đã gửi lời mời. Đang chờ {name} đồng ý…"
            )
        elif state == "accepting":
            self.invitation_var.set("Đang xác nhận cuộc trò chuyện…")
        elif state == "declining":
            self.invitation_var.set("Đang từ chối lời mời…")
        else:
            can_invite = (
                info["status"] in ("online", "away")
                and bool(info.get("ip"))
                and bool(info.get("tcp_port"))
            )
            reason = self._chat_reasons.get(username, "")
            self.invitation_var.set(
                reason
                or (
                    "Bắt đầu trò chuyện bằng cách gửi lời mời."
                    if can_invite
                    else "Người này hiện chưa có mặt trong danh sách."
                )
            )
            if can_invite:
                self.invite_button.pack(side="left")

    def _choose_file(self) -> None:
        """Giữ file đã chọn theo hội thoại, kể cả khi hủy hộp thoại lần sau."""
        username = self.current_chat
        choice = filedialog.askopenfilename(parent=self.root, title="Chọn file để gửi")
        if not choice or username != self.current_chat or self._chat_states.get(username) != "ready":
            return
        path = Path(choice)
        try:
            if not path.is_file():
                raise ValueError("File đã chọn không tồn tại.")
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ValueError(f"File vượt giới hạn {MAX_FILE_BYTES // (1024 * 1024)} MiB.")
        except (ValueError, OSError) as error:
            self.connection_notice_var.set(str(error))
            return
        self._file_drafts[username] = path
        self.connection_notice_var.set(f"Đã chọn {path.name} ({size:,} byte).")
        self._update_chat_controls()

    def _remove_file(self) -> None:
        """Bỏ file nháp của hội thoại đang mở."""
        self._file_drafts.pop(self.current_chat, None)
        self._update_chat_controls()

    def _send_file(self) -> None:
        """Giao file đã chọn cho worker của đúng phiên TCP."""
        username = self.current_chat
        path = self._file_drafts.get(username)
        if path is None or self.chat_network is None:
            return
        try:
            self.chat_network.offer_file(username, path, background=True)
        except RuntimeError as error:
            self.connection_notice_var.set(str(error))
            return
        self.connection_notice_var.set(f"Đang chuẩn bị {path.name} cho {username}…")
        self._remove_file()

    def _reply_file(self, accepted: bool) -> None:
        """Trả lời lần gửi đang hiện trên thẻ hội thoại."""
        username = self.current_chat
        offers = self._file_offers.get(username)
        if not offers or self.chat_network is None:
            return
        transfer_id = next(iter(offers))
        try:
            self.chat_network.reply_file(username, transfer_id, accepted)
        except (ValueError, RuntimeError) as error:
            self.connection_notice_var.set(str(error))
            return
        offer = offers.pop(transfer_id)
        status = "Đang chờ dữ liệu" if accepted else "Bạn đã từ chối"
        self._history.file_status(username, transfer_id, f"{offer['name']} · {status}", finished=not accepted)
        self._render_history()
        self._refresh_conversation_list()
        self._update_chat_controls()

    def _handle_file_event(self, kind: str, username: str, data: dict) -> None:
        """Cập nhật thao tác và lịch sử file của peer trên luồng Tk."""
        if kind == "file_prepare_error":
            path = Path(data["path"])
            self._file_drafts.setdefault(username, path)
            self.connection_notice_var.set(f"{path.name} · {data['reason']}")
            self._update_chat_controls()
            return
        name = data["name"]
        finished = False
        if kind == "file_offer":
            self._file_offers.setdefault(username, {})[data["transfer_id"]] = data
            status = "Chờ bạn trả lời"
            self.connection_notice_var.set(f"{username} muốn gửi {name}.")
            self._refresh_conversation_list()
            self._update_chat_controls()
        elif kind == "file_offered":
            status = f"Chờ {username} trả lời"
        elif kind == "file_reply":
            finished = not data["accepted"]
            status = "Đã từ chối" if finished else "Đã đồng ý nhận"
        elif kind == "file_progress":
            status = f"{data['percent']}%"
        elif kind == "file_sent":
            status, finished = f"100% · {username} đã lưu file", True
        elif kind == "file_received":
            status, finished = f"100% · Đã lưu tại {data['path']}", True
        elif kind == "file_error":
            status, finished = f"Lỗi: {data['reason']}", True
        else:
            return
        self._history.file_status(username, data["transfer_id"], f"{name} · {status}", finished=finished)

    def _on_invite(self) -> None:
        """Gửi lời mời trò chuyện tới peer đang được chọn trong giao diện."""
        if self.current_chat is None or self.chat_network is None:
            return

        peer = (
            self.discovery.get_peer(self.current_chat)
            if self.discovery is not None
            else None
        )
        if peer is None:
            self.connection_notice_var.set(
                "Không tìm thấy địa chỉ hiện tại của người này."
            )
            return

        try:
            self.chat_network.invite(peer)
        except (ValueError, RuntimeError) as error:
            self.connection_notice_var.set(str(error))

    def _on_accept_chat(self) -> None:
        """Chấp nhận lời mời trò chuyện từ người gửi của hội thoại hiện tại."""
        if self.current_chat is not None and self.chat_network is not None:
            self.chat_network.accept_chat(self.current_chat)

    def _on_decline_chat(self) -> None:
        """Từ chối lời mời trò chuyện hiện tại mà không xóa lịch sử tin nhắn."""
        if self.current_chat is not None and self.chat_network is not None:
            self.chat_network.decline_chat(self.current_chat)

    def _on_send(self, event: tk.Event | None = None) -> str:
        """Xử lý /leave, /quit hoặc gửi văn bản đến người đang chọn."""
        text = self.message_var.get()
        command = text.strip()

        if command == "/quit":
            self._on_close()
            return "break"

        username = self.current_chat
        if (
            not command
            or username is None
            or self.chat_network is None
            or self._chat_states.get(username) != "ready"
        ):
            return "break"

        try:
            if command == "/leave":
                self.chat_network.leave_chat(username)
            else:
                self.chat_network.send_text(username, text)
        except (ValueError, RuntimeError) as error:
            self.connection_notice_var.set(str(error))
        else:
            self.message_var.set("")
            self._drafts[username] = ""

        return "break"

    def run(self) -> None:
        """Chạy vòng lặp sự kiện chính của Tkinter."""
        self.root.mainloop()


if __name__ == "__main__":
    app = ChatWindow()
    app.run()
