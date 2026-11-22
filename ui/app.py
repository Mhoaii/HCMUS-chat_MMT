import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile, Peer
from network.tcp.chat_session import ChatSessionService
from network.tcp.tcp_service import TCPChatService
from network.udp.discovery_service import DiscoveryService


class ChatWindow:
    "quản lý cửa sổ và các thao tác"
    
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("LAN Chat")
        self.root.geometry("480x320")


        self.username_var = tk.StringVar()
        self.display_name_var = tk.StringVar()
        self.job_title_var = tk.StringVar()
        self.notice_var = tk.StringVar()
        self.notifications_var = tk.BooleanVar(value=True)

        self.tcp = TCPChatService()
        self.discovery: DiscoveryService | None = None
        self.profile: LocalProfile | None = None
        self._poll_id: str | None = None

        self.chat_network: ChatSessionService | None = None
        # Socket do service sở hữu; UI chỉ nhận dữ liệu để hiển thị.
        self._network_events: queue.Queue[
            tuple[str, str, dict]
        ] = queue.Queue()

        self._events_poll_id: str | None = None
        self._closing = threading.Event()

        self._network_event_lock = threading.Lock()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._on_close,
        )

        self._build_profile_form()

    def _build_profile_form(self) -> None:
        """Tạo ba ô nhập hồ sơ, nút Bắt đầu và dòng thông báo."""
        frame = ttk.Frame(self.root, padding=24)
        self.profile_frame = frame    
        frame.pack(fill="both", expand=True)

        # # Cột nhập liệu giãn theo chiều rộng cửa sổ.
        frame.columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Đăng nhập",
            font=("", 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(0, 20))

        ttk.Label(frame, text="Username:").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=6
        )
        username_entry = ttk.Entry(
            frame, textvariable=self.username_var
        )
        username_entry.grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Tên hiển thị:").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Entry(
            frame, textvariable=self.display_name_var
        ).grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Chức danh:").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Entry(
            frame, textvariable=self.job_title_var
        ).grid(row=3, column=1, sticky="ew", pady=6)

        ttk.Button(
            frame,
            text="Bắt đầu",
            command=self._on_start,
        ).grid(row=4, column=0, columnspan=2, pady=16)

        ttk.Label(
            frame,
            textvariable=self.notice_var,
            wraplength=360,
        ).grid(row=5, column=0, columnspan=2, sticky="w")

        username_entry.focus_set()

    def _on_start(self) -> None:
        """Kiểm tra hồ sơ, mở TCP/UDP rồi chuyển sang giao diện chat."""
        username = self.username_var.get().strip()

        if not username:
            self.notice_var.set("Bạn cần nhập username.")
            return

        self.username = username
        self.display_name = (
            self.display_name_var.get().strip() or username
        )
        self.job_title = (
            self.job_title_var.get().strip() or "Nhân viên"
        )

        try:
            actual_port = self.tcp.start(PORT_DEFAULT)

            self.profile = LocalProfile(
                username=self.username,
                display_name=self.display_name,
                job_title=self.job_title,
                tcp_port=actual_port,
                status=DEFAULT_STATUS,
            )

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
            self.notice_var.set(
                f"Không thể khởi động mạng: {error}"
            )
            return

        self.profile_frame.destroy()
        self._build_chat_view()
        self._refresh_online_peers()
        self._drain_network_events()

    def _on_close(self) -> None:
        """Dừng lịch UI và các service; service chat chịu trách nhiệm socket."""
        with self._network_event_lock:
            self._closing.set()

            while True:
                try:
                    self._network_events.get_nowait()
                except queue.Empty:
                    break

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
        "màng hình chính của khung chat"
        self.root.geometry("900x580")
        self.root.minsize(720, 460)

        self.chat_frame = ttk.Frame(self.root, padding= 12)
        self.chat_frame.pack(fill = "both", expand= True)

        frame = self.chat_frame
        frame.columnconfigure(1, weight = 1)
        frame.rowconfigure(1, weight = 1)

        header = ttk.Frame(frame)
        header.grid(
            row = 0, column = 0, columnspan=2,
            sticky= "ew", pady = (0, 12)
        )

        ttk.Label(
            header,
            text = f"{self.display_name}",
            font = ("", 12, "bold"),
        ).pack(side = "left")

        self.notifications_toggle = ttk.Checkbutton(
            header,
            text="Hiện thông báo",
            variable=self.notifications_var,
            command=self._on_notifications_toggled,
        )
        self.notifications_toggle.pack(side="left", padx=(16, 0))

        self.status_var = tk.StringVar(
            value=self.profile.status
        )

        self.status_box = ttk.Combobox(
            header,
            textvariable=self.status_var,
            values=("online", "away"),
            state="readonly",
            width=9,
        )
        self.status_box.pack(side="right")

        ttk.Label(
            header,
            text="Trạng thái:",
        ).pack(side="right", padx=(0, 6))

        self.status_box.bind(
            "<<ComboboxSelected>>",
            self._on_status_changed,
        )

        # col list: user and chat
        sidebar = ttk.Frame(frame)
        sidebar.grid(
            row = 1, column = 0, sticky = "ns", padx = (0, 12)
        )
        sidebar.columnconfigure(0, weight = 1)
        sidebar.rowconfigure(0, weight = 1)
        sidebar.rowconfigure(1, weight = 1)

        peers_frame = ttk.LabelFrame(
            sidebar, text = "User", padding = 8
        )
        peers_frame.grid(
            row = 0, column = 0, sticky = "nsew", pady = (0, 8)
        )

        self.peer_list = tk.Listbox(peers_frame, width = 24, height = 6, exportselection = False)
        self.peer_list.pack(fill="both", expand=True)

        recent_frame = ttk.LabelFrame(
            sidebar, text="Cuộc chat gần đây", padding=8
        )
        recent_frame.grid(row=1, column=0, sticky="nsew")

        self.conversation_list = tk.Listbox(
            recent_frame,
            width=24,
            height=6,
            exportselection=False,
        )
        self.conversation_list.pack(fill="both", expand=True)

        # Cột phải: tiêu đề, lịch sử và vùng soạn tin.
        conversation = ttk.Frame(frame)
        conversation.grid(row=1, column=1, sticky="nsew")
        conversation.columnconfigure(0, weight=1)
        conversation.rowconfigure(2, weight=1)

        self.chat_title_var = tk.StringVar(
            value="Chưa chọn người để chat"
        )
        ttk.Label(
            conversation,
            textvariable=self.chat_title_var,
            font=("", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Lời mời nằm trong hội thoại, không chiếm chỗ ở thanh toàn ứng dụng.
        self.invitation_frame = ttk.Frame(conversation, padding=8)
        self.invitation_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.invitation_var = tk.StringVar(
            value="Chọn một người trong danh sách để bắt đầu."
        )
        ttk.Label(
            self.invitation_frame, textvariable=self.invitation_var,
            wraplength=440, justify="left",
        ).pack(anchor="w")
        actions = ttk.Frame(self.invitation_frame)
        actions.pack(anchor="w", pady=(6, 0))
        self.invite_button = ttk.Button(
            actions, text="Mời trò chuyện", command=self._on_invite,
        )
        self.accept_button = ttk.Button(
            actions, text="Đồng ý", command=self._on_accept_chat,
        )
        self.decline_button = ttk.Button(
            actions, text="Từ chối", command=self._on_decline_chat,
        )

        self.history_text = ScrolledText(
            conversation,
            wrap="word",
            state="disabled",
            width=40,
            height=12,
        )
        self.history_text.grid(
            row=2, column=0, sticky="nsew"
        )

        composer = ttk.Frame(conversation)
        composer.grid(
            row=3, column=0, sticky="ew", pady=(8, 0)
        )
        composer.columnconfigure(0, weight=1)

        self.message_var = tk.StringVar()
        self.message_entry = ttk.Entry(
            composer, state="disabled", textvariable=self.message_var,
        )
        self.message_entry.bind("<Return>", self._on_send)
        self.message_entry.grid(
            row=0, column=0, sticky="ew"
        )

        self.send_button = ttk.Button(
            composer, text="Gửi", state="disabled", command=self._on_send,
        )
        self.send_button.grid(
            row=0, column=1, padx=(8, 0)
        )

        self.file_button = ttk.Button(
            composer, text="Chọn file", state="disabled"
        )
        self.file_button.grid(
            row=0, column=2, padx=(8, 0)
        )

        self.connection_notice_var = tk.StringVar(
            value="Chưa kết nối mạng."
        )
        ttk.Label(
            frame,
            textvariable=self.connection_notice_var,
            wraplength=660,
            justify="left",
        ).grid(
            row=2, column=0, columnspan=2,
            sticky="w", pady=(10, 0)
        )

        self._init_chat_data()
        self._update_chat_controls()

        self.peer_list.bind(
            "<<ListboxSelect>>",
            self._on_chat_selected,
        )
        self.conversation_list.bind(
            "<<ListboxSelect>>",
            self._on_chat_selected,
        )

        

    def _init_chat_data(self) -> None:
        """Tạo kho hội thoại rỗng; peer sẽ được cập nhật từ UDP."""
        self.current_chat: str | None = None

        self._peer_info: dict[str, dict] = {}
        self._peer_order: list[str] = []
        self._conversation_order: list[str] = []

        self.chat_history: dict[str, list[tuple[str, str]]] = {}
        self.unread_count: dict[str, int] = {}
        self._chat_states: dict[str, str] = {}
        self._chat_reasons: dict[str, str] = {}
        self._drafts: dict[str, str] = {}

        self._peer_snapshot = None

        self.peer_list.delete(0, tk.END)
        self.conversation_list.delete(0, tk.END)


    def _on_chat_selected(self, event: tk.Event) -> None:
        """Đọc dòng được chọn từ sự kiện và mở cuộc chat tương ứng."""
        source = event.widget
        selected = source.curselection()

        # Bỏ chọn dòng cũng có thể phát sự kiện; khi đó không làm gì.
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
        """Mở lịch sử peer đã biết; giữ cuộc chat khi peer offline."""
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
        """Vẽ lại lịch sử của cuộc chat đang chọn rồi khóa chỉnh sửa."""
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", tk.END)

        if self.current_chat is not None:
            messages = self.chat_history.get(
                self.current_chat, []
            )

            for sender, text in messages:
                self.history_text.insert(
                    tk.END,
                    f"{sender}: {text}\n\n",
                )

        self.history_text.configure(state="disabled")
        self.history_text.see(tk.END)

    def _receive_message(
        self,
        username: str,
        text: str,
    ) -> None:
        """Lưu tin vào hội thoại và cập nhật unread; chỉ gọi trên luồng UI."""
        if not text.strip():
            return

        # Tin TCP có thể đến trước lượt cập nhật danh sách UDP.
        peer = self._peer_info.setdefault(
            username,
            {
                "display_name": username,
                "status": "chưa có presence",
                "ip": None,
                "tcp_port": None,
            },
        )

        self.chat_history.setdefault(username, []).append(
            (peer["display_name"], text)
        )
        self.unread_count.setdefault(username, 0)

        # Tin từ người chưa từng mở cũng phải có trong danh sách hội thoại.
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
        """Vẽ tên và số chưa đọc, giữ dòng đang được chọn nếu có."""
        selected = self.conversation_list.curselection()

        self.conversation_list.delete(0, tk.END)

        for username in self._conversation_order:
            name = self._peer_info[username]["display_name"]
            count = self.unread_count[username]

            label = f"{name} ({count})" if count else name
            state = self._chat_states.get(username)
            if state == "incoming":
                label += " · Lời mời"
            elif state in ("connecting", "waiting", "accepting"):
                label += " · Đang chờ"
            self.conversation_list.insert(tk.END, label)

        # Bước này giữ nguyên thứ tự danh sách nên có thể chọn lại dòng cũ.
        if selected:
            self.conversation_list.selection_set(selected[0])
    
    def _refresh_online_peers(self) -> None:
        """Lấy snapshot UDP và cập nhật User trên luồng giao diện."""
        if self.discovery is None:
            return

        peers = sorted(
            self.discovery.list_peers(),
            key=lambda peer: peer.username,
        )

        # Không đưa last_seen vào để tránh vẽ lại chỉ vì nhận presence mới.
        snapshot = [
            (
                peer.username,
                peer.display_name,
                peer.status,
                peer.ip,
                peer.tcp_port,
            )
            for peer in peers
        ]

        if snapshot != self._peer_snapshot:
            # So sánh trước khi thay danh sách cũ bằng snapshot mới.
            presence_notice = self._presence_notification(peers)
            selected = self.peer_list.curselection()
            selected_username = (
                self._peer_order[selected[0]]
                if selected
                else None
            )

            online = {peer.username for peer in peers}

            # Giữ thông tin peer cũ, chỉ đổi trạng thái khi hết hiện diện.
            for username, info in self._peer_info.items():
                if username not in online:
                    info["status"] = "offline"

            for peer in peers:
                self._peer_info[peer.username] = {
                    "display_name": peer.display_name,
                    "status": peer.status,
                    "ip": peer.ip,
                    "tcp_port": peer.tcp_port,
                }

                # Chỉ khởi tạo nếu chưa có, không ghi đè dữ liệu cũ.
                self.chat_history.setdefault(peer.username, [])
                self.unread_count.setdefault(peer.username, 0)

            self._peer_order = [
                peer.username for peer in peers
            ]

            self.peer_list.delete(0, tk.END)

            for peer in peers:
                self.peer_list.insert(
                    tk.END,
                    f"{peer.display_name} ({peer.username})"
                    f" · {peer.status}",
                )

            # Giữ người đang chọn dù vị trí dòng có thay đổi.
            if selected_username in self._peer_order:
                index = self._peer_order.index(
                    selected_username
                )
                self.peer_list.selection_set(index)

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

            self._peer_snapshot = snapshot
            self._update_chat_controls()

        self._poll_id = self.root.after(
            500,
            self._refresh_online_peers,
        )

    def _on_status_changed(
        self,
        event: tk.Event | None = None,
    ) -> None:
        """Đổi online/away qua DiscoveryService; báo lỗi nếu trạng thái sai."""
        if self.discovery is None or self.profile is None:
            return

        new_status = self.status_var.get()

        try:
            self.discovery.set_status(new_status)

        except ValueError:
            # Khôi phục lựa chọn về trạng thái hợp lệ của hồ sơ.
            self.status_var.set(self.profile.status)

            self.connection_notice_var.set(
                "Trạng thái chỉ được là online hoặc away."
            )
            return

        self.connection_notice_var.set(
            f"Đã đặt trạng thái: {new_status}. "
            "Sẽ phát trong gói UDP tiếp theo."
        )

    def _presence_notification(self, peers: list[Peer]) -> str:
        """Trả thông báo peer xuất hiện/hết hạn, hoặc chuỗi rỗng khi tắt."""
        if not self.notifications_var.get():
            return ""

        previous = set(self._peer_order)
        current = {peer.username: peer for peer in peers}
        current_names = set(current)
        messages = []

        for username in sorted(current_names - previous):
            peer = current[username]
            messages.append(
                f"{peer.display_name} ({username}) "
                f"vừa xuất hiện · {peer.status}."
            )

        for username in sorted(previous - current_names):
            name = self._peer_info[username]["display_name"]
            messages.append(
                f"{name} ({username}) "
                "went offline"
            )

        return " ".join(messages)

    def _show_network_summary(self) -> None:
        """Hiện cổng TCP và số peer đang có trên dòng trạng thái."""
        if self.profile is None:
            return

        self.connection_notice_var.set(
            f"UDP đang chạy · TCP port: {self.profile.tcp_port}"
            f" · {len(self._peer_order)} peer hiện diện."
        )

    def _on_notifications_toggled(self) -> None:
        """Áp dụng lựa chọn bật/tắt từ sự kiện kế tiếp, xóa thông báo cũ."""
        self._show_network_summary()

    def post_network_event(
        self, event_type: str, username: str, data: dict | str = "",
    ) -> None:
        """Nhận dữ liệu từ worker; mọi cập nhật widget diễn ra khi drain."""
        with self._network_event_lock:
            if not self._closing.is_set():
                payload = data if isinstance(data, dict) else {"text": data}
                self._network_events.put((event_type, username, payload))

    def _remember_chat_peer(self, username: str, data: dict) -> None:
        """Tạo hội thoại từ TCP kể cả khi lượt cập nhật UDP chưa đến."""
        info = self._peer_info.setdefault(username, {
            "display_name": username, "status": "chưa có presence",
            "ip": None, "tcp_port": None,
        })
        if data.get("display_name"):
            info["display_name"] = data["display_name"]
        for key in ("ip", "tcp_port"):
            if not info.get(key) and data.get(key):
                info[key] = data[key]
        self.chat_history.setdefault(username, [])
        self.unread_count.setdefault(username, 0)
        if username not in self._conversation_order:
            self._conversation_order.append(username)

    def _drain_network_events(self) -> None:
        """Xử lý lời mời, trạng thái và tin trên luồng UI, tối đa 50 mỗi lượt."""
        self._events_poll_id = None
        if self._closing.is_set():
            return
        for _ in range(50):
            try:
                event_type, username, data = self._network_events.get_nowait()
            except queue.Empty:
                break

            if event_type == "chat_state":
                self._remember_chat_peer(username, data)
                self._chat_states[username] = data["state"]
                self._chat_reasons[username] = data.get("reason", "")
                if data["state"] == "incoming":
                    name = self._peer_info[username]["display_name"]
                    self.connection_notice_var.set(
                        f"{name} muốn trò chuyện. Chọn hội thoại để trả lời."
                    )
                self._refresh_conversation_list()
                self._update_chat_controls()

            elif event_type == "message":
                self._receive_message(username, data["text"])

            elif event_type == "sent":
                self._remember_chat_peer(username, data)
                self.chat_history[username].append(("Bạn", data["text"]))
                if self.current_chat == username:
                    self._render_history()
                self._refresh_conversation_list()

            elif event_type == "send_failed":
                text = data["text"]
                draft = (
                    self.message_var.get() if self.current_chat == username
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

        self._events_poll_id = self.root.after(
            100, self._drain_network_events,
        )

    def _update_chat_controls(self) -> None:
        """Hiện lời mời hoặc vùng soạn tin theo hội thoại, độc lập presence."""
        username = self.current_chat
        state = self._chat_states.get(username, "idle")
        for button in (
            self.invite_button, self.accept_button, self.decline_button,
        ):
            button.pack_forget()

        ready = state == "ready"
        self.message_entry.configure(state="normal" if ready else "disabled")
        self.send_button.configure(state="normal" if ready else "disabled")
        if ready:
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
                and bool(info.get("ip")) and bool(info.get("tcp_port"))
            )
            reason = self._chat_reasons.get(username, "")
            self.invitation_var.set(reason or (
                "Bắt đầu trò chuyện bằng cách gửi lời mời."
                if can_invite else "Người này hiện chưa có mặt trong danh sách."
            ))
            if can_invite:
                self.invite_button.pack(side="left")

    def _on_invite(self) -> None:
        """Mời người đang chọn qua endpoint hiện tại của DiscoveryService."""
        if self.current_chat is None or self.chat_network is None:
            return
        peer = (
            self.discovery.get_peer(self.current_chat)
            if self.discovery is not None else None
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
        """Đồng ý lời mời của hội thoại đang mở."""
        if self.current_chat is not None and self.chat_network is not None:
            self.chat_network.accept_chat(self.current_chat)

    def _on_decline_chat(self) -> None:
        """Từ chối lời mời mà không xóa lịch sử hội thoại."""
        if self.current_chat is not None and self.chat_network is not None:
            self.chat_network.decline_chat(self.current_chat)

    def _on_send(self, event: tk.Event | None = None) -> str:
        """Gửi qua writer nền; chỉ thêm lịch sử khi thao tác gửi thành công."""
        username = self.current_chat
        text = self.message_var.get()
        if (
            username is None or self.chat_network is None
            or self._chat_states.get(username) != "ready" or not text.strip()
        ):
            return "break"
        try:
            self.chat_network.send_text(username, text)
        except (ValueError, RuntimeError) as error:
            self.connection_notice_var.set(str(error))
        else:
            self.message_var.set("")
            self._drafts[username] = ""
        return "break"

    def run(self) -> None:
        """Chạy vòng xử lý sự kiện cho tới khi đóng cửa sổ."""
        self.root.mainloop()


if __name__ == "__main__":
    app = ChatWindow()
    app.run()
