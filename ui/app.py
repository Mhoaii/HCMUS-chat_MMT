import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile
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

        self.tcp = TCPChatService()
        self.discovery: DiscoveryService | None = None
        self.profile: LocalProfile | None = None
        self._poll_id: str | None = None

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

        except (OSError, ValueError, RuntimeError) as error:
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

    def _on_close(self) -> None:
        """Hủy lịch cập nhật, dừng UDP/TCP và đóng cửa sổ."""
        if self._poll_id is not None:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None

        try:
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

        ttk.Label(
            header, text = "Status: away",
        ).pack(side = "right")

        self.demo_receive_button = ttk.Button(
            header,
            text="Thử nhận từ Huy (mẫu)",
            command=lambda: self._receive_message(
                "demo_huy",
                "Bạn có rảnh để họp nhóm không?",
            ),
        )
        self.demo_receive_button.pack(
            side="right",
            padx=12,
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
        conversation.rowconfigure(1, weight=1)

        self.chat_title_var = tk.StringVar(
            value="Chưa chọn người để chat"
        )
        ttk.Label(
            conversation,
            textvariable=self.chat_title_var,
            font=("", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.history_text = ScrolledText(
            conversation,
            wrap="word",
            state="disabled",
            width=40,
            height=12,
        )
        self.history_text.grid(
            row=1, column=0, sticky="nsew"
        )

        composer = ttk.Frame(conversation)
        composer.grid(
            row=2, column=0, sticky="ew", pady=(8, 0)
        )
        composer.columnconfigure(0, weight=1)

        self.message_entry = ttk.Entry(
            composer, state="disabled"
        )
        self.message_entry.grid(
            row=0, column=0, sticky="ew"
        )

        self.send_button = ttk.Button(
            composer, text="Gửi", state="disabled"
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
            frame, textvariable=self.connection_notice_var
        ).grid(
            row=2, column=0, columnspan=2,
            sticky="w", pady=(10, 0)
        )

        self._init_chat_data()
        self.demo_receive_button.configure(state="disabled")

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
        self.current_chat = username
        peer = self._peer_info[username]

        if username not in self._conversation_order:
            self._conversation_order.append(username)

        self.chat_title_var.set(
            f"{peer['display_name']} · {peer['status']}"
        )

        self._render_history()

        self.unread_count[username] = 0
        self._refresh_conversation_list()

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

    def _receive_message(self, username: str, text: str) -> None:
        """Nhận tin cho peer mẫu đã biết; cập nhật lịch sử/unread trên luồng UI."""
        if not text.strip():
            return

        peer = self._demo_peers[username]

        self.chat_history[username].append(
            (peer["display_name"], text)
        )

        if username == self.current_chat:
            self._render_history()
        else:
            self.unread_count[username] += 1

        self._refresh_conversation_list()

        self.connection_notice_var.set(
            f"Dữ liệu mẫu — vừa thêm tin của "
            f"{peer['display_name']}; chưa kết nối mạng."
        )


    def _refresh_conversation_list(self) -> None:
        """Vẽ tên và số chưa đọc, giữ dòng đang được chọn nếu có."""
        selected = self.conversation_list.curselection()

        self.conversation_list.delete(0, tk.END)

        for username in self._conversation_order:
            name = self._peer_info[username]["display_name"]
            count = self.unread_count[username]

            label = f"{name} ({count})" if count else name
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

            self.connection_notice_var.set(
                f"UDP đang chạy · TCP port: {self.profile.tcp_port}"
                f" · {len(peers)} peer hiện diện."
                " Chưa tích hợp chat TCP."
            )

            self._peer_snapshot = snapshot

        self._poll_id = self.root.after(
            500,
            self._refresh_online_peers,
        )

    def run(self) -> None:
        """Chạy vòng xử lý sự kiện cho tới khi đóng cửa sổ."""
        self.root.mainloop()


if __name__ == "__main__":
    app = ChatWindow()
    app.run()
