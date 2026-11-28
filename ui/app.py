"""Giao diện desktop Tkinter cho ứng dụng LAN Chat P2P.

Module này quản lý cửa sổ đăng nhập, danh sách peer UDP, danh sách hội thoại,
banner lời mời TCP và khung lịch sử tin nhắn. Toàn bộ màu sắc và kiểu dáng
được điều phối tập trung qua `ui.theme.ThemeManager` (hỗ trợ Light/Dark Mode).
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from config import DEFAULT_STATUS, PORT_DEFAULT
from models.peer import LocalProfile, Peer
from network.tcp.chat_session import ChatSessionService
from network.tcp.tcp_service import TCPChatService
from network.udp.discovery_service import DiscoveryService
from ui.message_history import MessageHistory
from ui.theme import (
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
    ThemeManager,
    create_app_icon,
)


class ChatWindow:
    """Quản lý cửa sổ chính, trạng thái UI và cầu nối sự kiện mạng.

    Mục đích và trách nhiệm:
        - Hiển thị màn hình đăng nhập hồ sơ và chuyển sang giao diện chat chính.
        - Điều phối việc khởi động/dừng `TCPChatService`, `DiscoveryService` và
          `ChatSessionService` theo vòng đời cửa sổ.
        - Nhận sự kiện từ các worker mạng qua `queue.Queue` và chỉ cập nhật
          widget trên luồng chính của Tkinter.
        - Đồng bộ giao diện Light/Dark Mode qua `ThemeManager`.

    Lưu ý:
        Giữ nguyên các thuộc tính công khai và tên widget mà `ChatWindowTests`
        đang kiểm thử (`profile_frame`, `peer_list`, `conversation_list`,
        `invitation_frame`, `invite_button`, `accept_button`, `decline_button`,
        `message_entry`, `send_button`, `message_var`, `notifications_var`,
        `connection_notice_var`, `chat_history`, `unread_count`, `_chat_states`).
    """

    def __init__(self) -> None:
        """Khởi tạo cửa sổ gốc, hệ thống theme, biến trạng thái và form đăng nhập.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        self.root = tk.Tk()
        self.root.title("LAN Chat P2P")
        self.root.minsize(460, 420)

        # Quản lý Light/Dark Mode tập trung cho toàn bộ ứng dụng.
        self.theme = ThemeManager(initial_mode="light")
        self.theme_toggle_var = tk.StringVar(value=self.theme.toggle_label)
        self.theme.apply_ttk_styles(self.root)

        # Thay icon lông vũ mặc định của Tk bằng icon tối giản của ứng dụng.
        self._app_icon = create_app_icon(self.root, self.theme.palette.accent)
        self.root.iconphoto(True, self._app_icon)

        # Căn giữa cửa sổ đăng nhập trên màn hình và đồng bộ viền Windows DWM.
        self._center_window(540, 480)
        self.theme.apply_window_chrome(self.root)
        self.root.after_idle(
            lambda: self.theme.apply_window_chrome(self.root)
        )

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

        # Tham chiếu các widget tk thuần cần tô màu lại khi đổi Light/Dark Mode.
        self._status_dot_label: tk.Label | None = None
        self.peer_list: tk.Listbox | None = None
        self.conversation_list: tk.Listbox | None = None
        self.history_text: ScrolledText | None = None
        self._peer_count_var: tk.StringVar | None = None
        self._chat_subtitle_var: tk.StringVar | None = None

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._on_close,
        )

        self._build_profile_form()

    def _center_window(self, width: int, height: int) -> None:
        """Đặt kích thước và căn cửa sổ ra chính giữa màn hình hiện tại.

        Tham số đầu vào:
            width (int): Chiều rộng cửa sổ tính theo pixel.
            height (int): Chiều cao cửa sổ tính theo pixel.

        Giá trị trả về:
            None
        """
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def _on_toggle_theme(self) -> None:
        """Chuyển đổi qua lại giữa Light Mode và Dark Mode cho toàn ứng dụng.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None

        Cách hoạt động:
            Đảo chế độ trong `ThemeManager`, cập nhật nhãn nút bấm và áp dụng
            lại màu cho cả widget `ttk` lẫn widget `tk` thuần.
        """
        self.theme.toggle()
        self.theme_toggle_var.set(self.theme.toggle_label)
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Áp dụng bảng màu hiện tại cho toàn bộ widget ttk và tk đang tồn tại.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None

        Cách hoạt động:
            1. Gọi `ThemeManager.apply_ttk_styles(self.root)` để cập nhật tất cả
               widget `ttk` theo style đã đăng ký.
            2. Tô màu thủ công cho các widget `tk` thuần (`Listbox`,
               `ScrolledText`, nhãn chấm trạng thái) vì chúng không ăn theo
               `ttk.Style`.
            3. Cập nhật lại màu tag bong bóng tin nhắn trong khung lịch sử.
        """
        self.theme.apply_ttk_styles(self.root)
        self.theme.apply_window_chrome(self.root)
        p = self.theme.palette

        # Cập nhật màu cho hai Listbox ở sidebar nếu màn hình chat đã được tạo.
        for listbox in (self.peer_list, self.conversation_list):
            if listbox is not None and listbox.winfo_exists():
                listbox.configure(
                    bg=p.bg_input,
                    fg=p.text_primary,
                    selectbackground=p.bg_selected,
                    selectforeground=p.text_primary,
                    highlightbackground=p.border,
                    highlightcolor=p.border_focus,
                )

        # Cập nhật màu cho khung lịch sử chat và các tag bong bóng tin nhắn.
        if self.history_text is not None and self.history_text.winfo_exists():
            self.history_text.configure(
                bg=p.bg_surface,
                fg=p.text_primary,
                insertbackground=p.text_primary,
                selectbackground=p.bg_selected,
                selectforeground=p.text_primary,
            )
            self._configure_history_tags()

        # Cập nhật chấm màu trạng thái trên thanh header.
        self._refresh_status_dot()

    def _refresh_status_dot(self) -> None:
        """Cập nhật màu sắc chấm trạng thái online/away trên thanh header.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        if (
            self._status_dot_label is None
            or not self._status_dot_label.winfo_exists()
        ):
            return
        p = self.theme.palette
        current_status = (
            self.status_var.get()
            if hasattr(self, "status_var")
            else DEFAULT_STATUS
        )
        dot_color = (
            p.status_online if current_status == "online" else p.status_away
        )
        self._status_dot_label.configure(
            bg=p.bg_app,
            fg=dot_color,
        )

    def _configure_history_tags(self) -> None:
        """Cấu hình tag định dạng bong bóng tin nhắn cho `ScrolledText`.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None

        Cách hoạt động:
            Tạo các tag riêng cho tên người gửi và nội dung tin nhắn của "Bạn"
            (căn phải, nền màu nhấn) và "Đối phương" (căn trái, nền bề mặt dịu),
            cùng tag gợi ý khi khung chat chưa có tin nhắn nào.
        """
        if self.history_text is None:
            return
        p = self.theme.palette

        # Nhãn tên người gửi của chính mình (căn phải, chữ nhỏ màu phụ).
        self.history_text.tag_configure(
            "self_sender",
            justify="right",
            foreground=p.text_secondary,
            font=FONT_SMALL,
            rmargin=10,
            spacing1=8,
            spacing3=2,
        )
        # Nội dung tin nhắn của chính mình (nền màu nhấn, lề trái rộng để tạo khối bên phải).
        self.history_text.tag_configure(
            "self_bubble",
            justify="right",
            background=p.bubble_self_bg,
            foreground=p.bubble_self_fg,
            font=FONT_BODY,
            lmargin1=130,
            lmargin2=130,
            rmargin=10,
            spacing1=6,
            spacing2=2,
            spacing3=8,
        )

        # Nhãn tên đối phương (căn trái, chữ nhỏ đậm).
        self.history_text.tag_configure(
            "peer_sender",
            justify="left",
            foreground=p.text_secondary,
            font=FONT_SMALL,
            lmargin1=10,
            lmargin2=10,
            spacing1=8,
            spacing3=2,
        )
        # Nội dung tin nhắn đối phương (nền xám dịu, lề phải rộng để tạo khối bên trái).
        self.history_text.tag_configure(
            "peer_bubble",
            justify="left",
            background=p.bubble_peer_bg,
            foreground=p.bubble_peer_fg,
            font=FONT_BODY,
            lmargin1=10,
            lmargin2=10,
            rmargin=130,
            spacing1=6,
            spacing2=2,
            spacing3=8,
        )

        # Dòng khoảng trắng nhỏ ngăn cách giữa các tin nhắn.
        self.history_text.tag_configure(
            "spacer",
            font=(FONT_BODY[0], 4),
        )

        # Gợi ý ở giữa khi chưa chọn người hoặc chưa có tin nhắn.
        self.history_text.tag_configure(
            "empty_hint",
            justify="center",
            foreground=p.text_muted,
            font=FONT_BODY,
            spacing1=48,
        )

    def _build_profile_form(self) -> None:
        """Tạo màn hình đăng nhập dạng thẻ căn giữa với nút chuyển Sáng/Tối.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None

        Cách hoạt động:
            Đặt thanh trên cùng chứa nút chuyển Sáng/Tối và một khung thẻ
            (`Card.TFrame`) căn giữa chứa ba trường nhập hồ sơ, nút bắt đầu
            và dòng hiển thị lỗi. Nhấn Enter ở bất kỳ ô nhập nào đều kích hoạt
            `_on_start()`.
        """
        frame = ttk.Frame(self.root, style="App.TFrame", padding=24)
        self.profile_frame = frame
        frame.pack(fill="both", expand=True)

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Thanh công cụ nhỏ phía trên cho nút chuyển Sáng/Tối.
        top_bar = ttk.Frame(frame, style="App.TFrame")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(
            top_bar,
            text="HCMUS · Mạng máy tính",
            style="HeaderMuted.TLabel",
        ).pack(side="left")
        ttk.Button(
            top_bar,
            textvariable=self.theme_toggle_var,
            style="Secondary.TButton",
            command=self._on_toggle_theme,
        ).pack(side="right")

        # Thẻ đăng nhập căn giữa.
        card_wrap = ttk.Frame(frame, style="App.TFrame")
        card_wrap.grid(row=1, column=0, sticky="nsew")
        card_wrap.columnconfigure(0, weight=1)
        card_wrap.rowconfigure(0, weight=1)

        card = ttk.Frame(card_wrap, style="Card.TFrame", padding=(28, 24))
        card.grid(row=0, column=0, sticky="ew", padx=20)
        card.columnconfigure(0, weight=1)

        ttk.Label(
            card,
            text="LAN Chat P2P",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            card,
            text="Kết nối ngang hàng trong mạng nội bộ qua UDP & TCP.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 18))

        # Trường 1: Username (bắt buộc).
        ttk.Label(
            card,
            text="Username *",
            style="Surface.TLabel",
            font=FONT_BODY_BOLD,
        ).grid(row=2, column=0, sticky="w", pady=(0, 4))
        username_entry = ttk.Entry(
            card,
            textvariable=self.username_var,
            style="Modern.TEntry",
            font=FONT_BODY,
        )
        username_entry.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        # Trường 2: Tên hiển thị.
        ttk.Label(
            card,
            text="Tên hiển thị",
            style="Surface.TLabel",
            font=FONT_BODY_BOLD,
        ).grid(row=4, column=0, sticky="w", pady=(0, 4))
        display_entry = ttk.Entry(
            card,
            textvariable=self.display_name_var,
            style="Modern.TEntry",
            font=FONT_BODY,
        )
        display_entry.grid(row=5, column=0, sticky="ew", pady=(0, 12))

        # Trường 3: Chức danh.
        ttk.Label(
            card,
            text="Chức danh",
            style="Surface.TLabel",
            font=FONT_BODY_BOLD,
        ).grid(row=6, column=0, sticky="w", pady=(0, 4))
        job_entry = ttk.Entry(
            card,
            textvariable=self.job_title_var,
            style="Modern.TEntry",
            font=FONT_BODY,
        )
        job_entry.grid(row=7, column=0, sticky="ew", pady=(0, 18))

        # Hỗ trợ nhấn Enter ở bất kỳ ô nhập nào để vào chat nhanh.
        for entry in (username_entry, display_entry, job_entry):
            entry.bind("<Return>", lambda _event: self._on_start())

        ttk.Button(
            card,
            text="Bắt đầu trò chuyện",
            style="Primary.TButton",
            command=self._on_start,
        ).grid(row=8, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(
            card,
            textvariable=self.notice_var,
            style="Error.TLabel",
            wraplength=380,
            justify="left",
        ).grid(row=9, column=0, sticky="w")

        username_entry.focus_set()

    def _on_start(self) -> None:
        """Kiểm tra hồ sơ, mở TCP/UDP rồi chuyển sang giao diện chat chính.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None

        Cách hoạt động:
            Kiểm tra username không rỗng, mở cổng TCP, khởi tạo `LocalProfile`,
            bật `DiscoveryService` và `ChatSessionService`. Nếu có lỗi mạng thì
            thu hồi tài nguyên đã mở và hiển thị thông báo trên form đăng nhập.
        """
        username = self.username_var.get().strip()

        if not username:
            self.notice_var.set("Bạn cần nhập username để bắt đầu.")
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
        """Dừng lịch UI, thu hồi các service mạng và đóng cửa sổ an toàn.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
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
        """Xây dựng giao diện chat chính gồm Header, Sidebar, Hội thoại và Status bar.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None

        Cách hoạt động:
            Tổ chức cửa sổ theo bố cục 3 tầng rõ ràng:
            - Hàng 0: Header chứa thông tin cá nhân, chọn trạng thái online/away,
              bật/tắt thông báo presence và nút chuyển Sáng/Tối.
            - Hàng 1: Vùng làm việc chính gồm Sidebar (danh sách User + Cuộc chat
              gần đây) và khung Hội thoại (tiêu đề, banner lời mời, lịch sử bong
              bóng, thanh soạn tin).
            - Hàng 2: Thanh trạng thái mạng phía dưới.
        """
        self._center_window(1040, 660)
        self.root.minsize(820, 520)

        self.chat_frame = ttk.Frame(self.root, style="App.TFrame")
        self.chat_frame.pack(fill="both", expand=True)

        frame = self.chat_frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        # --- TẦNG 1: HEADER ---
        header = ttk.Frame(frame, style="App.TFrame", padding=(18, 12))
        header.grid(row=0, column=0, sticky="ew")

        user_info = ttk.Frame(header, style="App.TFrame")
        user_info.pack(side="left")

        job_title = (
            self.profile.job_title
            if self.profile is not None
            else getattr(self, "job_title", "Nhân viên")
        )
        ttk.Label(
            user_info,
            text=f"{self.display_name}",
            style="Header.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            user_info,
            text=f"@{self.username} · {job_title}",
            style="HeaderMuted.TLabel",
        ).pack(anchor="w")

        # Cụm điều khiển bên phải header.
        controls = ttk.Frame(header, style="App.TFrame")
        controls.pack(side="right")

        ttk.Button(
            controls,
            textvariable=self.theme_toggle_var,
            style="Secondary.TButton",
            command=self._on_toggle_theme,
        ).pack(side="right", padx=(12, 0))

        self.status_var = tk.StringVar(
            value=self.profile.status if self.profile is not None else DEFAULT_STATUS
        )
        self.status_box = ttk.Combobox(
            controls,
            textvariable=self.status_var,
            values=("online", "away"),
            state="readonly",
            style="Modern.TCombobox",
            width=9,
            font=FONT_BODY,
        )
        self.status_box.pack(side="right")
        self.status_box.bind(
            "<<ComboboxSelected>>",
            self._on_status_changed,
        )

        # Chấm tròn màu chỉ báo trực quan trạng thái bản thân.
        self._status_dot_label = tk.Label(
            controls,
            text="●",
            font=(FONT_BODY[0], 11),
            bd=0,
        )
        self._status_dot_label.pack(side="right", padx=(12, 4))

        ttk.Label(
            controls,
            text="Trạng thái:",
            style="HeaderMuted.TLabel",
        ).pack(side="right", padx=(12, 0))

        self.notifications_toggle = ttk.Checkbutton(
            controls,
            text="Hiện thông báo",
            variable=self.notifications_var,
            style="Header.TCheckbutton",
            command=self._on_notifications_toggled,
        )
        self.notifications_toggle.pack(side="right", padx=(0, 8))

        # Đường kẻ phân tách header và vùng nội dung.
        ttk.Frame(frame, style="Divider.TFrame", height=1).grid(
            row=1, column=0, sticky="ew"
        )

        # --- TẦNG 2: VÙNG LÀM VIỆC CHÍNH (SIDEBAR + HỘI THOẠI) ---
        body = ttk.Frame(frame, style="App.TFrame")
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        # Cột trái: Sidebar danh sách peer & hội thoại gần đây.
        sidebar = ttk.Frame(body, style="Sidebar.TFrame", padding=(14, 14))
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(1, weight=1)
        sidebar.rowconfigure(3, weight=1)

        self._peer_count_var = tk.StringVar(value="NGƯỜI DÙNG TRONG LAN (0)")
        ttk.Label(
            sidebar,
            textvariable=self._peer_count_var,
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.peer_list = tk.Listbox(
            sidebar,
            width=28,
            height=8,
            exportselection=False,
            bd=0,
            highlightthickness=1,
            activestyle="none",
            font=FONT_BODY,
            relief="flat",
        )
        self.peer_list.grid(row=1, column=0, sticky="nsew", pady=(0, 14))

        ttk.Label(
            sidebar,
            text="CUỘC CHAT GẦN ĐÂY",
            style="Section.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(0, 6))

        self.conversation_list = tk.Listbox(
            sidebar,
            width=28,
            height=8,
            exportselection=False,
            bd=0,
            highlightthickness=1,
            activestyle="none",
            font=FONT_BODY,
            relief="flat",
        )
        self.conversation_list.grid(row=3, column=0, sticky="nsew")

        # Đường kẻ dọc phân tách sidebar và khung hội thoại.
        ttk.Frame(body, style="Divider.TFrame", width=1).grid(
            row=0, column=1, sticky="ns"
        )

        # Cột phải: Khung hội thoại.
        conversation = ttk.Frame(body, style="Surface.TFrame")
        conversation.grid(row=0, column=2, sticky="nsew")
        conversation.columnconfigure(0, weight=1)
        conversation.rowconfigure(3, weight=1)

        # Tiêu đề cuộc trò chuyện hiện tại.
        chat_header = ttk.Frame(
            conversation, style="Surface.TFrame", padding=(18, 12)
        )
        chat_header.grid(row=0, column=0, sticky="ew")

        self.chat_title_var = tk.StringVar(
            value="Chưa chọn người để chat"
        )
        ttk.Label(
            chat_header,
            textvariable=self.chat_title_var,
            style="Heading.TLabel",
        ).pack(anchor="w")

        self._chat_subtitle_var = tk.StringVar(
            value="Chọn một người ở danh sách bên trái để xem lịch sử hoặc gửi lời mời."
        )
        ttk.Label(
            chat_header,
            textvariable=self._chat_subtitle_var,
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        ttk.Frame(conversation, style="Divider.TFrame", height=1).grid(
            row=1, column=0, sticky="ew"
        )

        # Banner lời mời nằm gọn trong hội thoại, tự ẩn khi phiên đã sẵn sàng.
        self.invitation_frame = ttk.Frame(
            conversation, style="Banner.TFrame", padding=(18, 12)
        )
        self.invitation_frame.grid(row=2, column=0, sticky="ew")
        self.invitation_var = tk.StringVar(
            value="Chọn một người trong danh sách để bắt đầu."
        )
        ttk.Label(
            self.invitation_frame,
            textvariable=self.invitation_var,
            style="Banner.TLabel",
            wraplength=540,
            justify="left",
        ).pack(anchor="w")

        actions = ttk.Frame(self.invitation_frame, style="Banner.TFrame")
        actions.pack(anchor="w", pady=(8, 0))
        self.invite_button = ttk.Button(
            actions,
            text="Mời trò chuyện",
            style="Primary.TButton",
            command=self._on_invite,
        )
        self.accept_button = ttk.Button(
            actions,
            text="Đồng ý",
            style="Primary.TButton",
            command=self._on_accept_chat,
        )
        self.decline_button = ttk.Button(
            actions,
            text="Từ chối",
            style="Danger.TButton",
            command=self._on_decline_chat,
        )

        # Khung hiển thị lịch sử tin nhắn dạng bong bóng.
        self.history_text = ScrolledText(
            conversation,
            wrap="word",
            state="disabled",
            width=40,
            height=12,
            bd=0,
            highlightthickness=0,
            padx=14,
            pady=12,
            font=FONT_BODY,
            cursor="arrow",
        )
        self.history_text.grid(row=3, column=0, sticky="nsew")

        ttk.Frame(conversation, style="Divider.TFrame", height=1).grid(
            row=4, column=0, sticky="ew"
        )

        # Thanh soạn tin nhắn phía dưới khung hội thoại.
        composer = ttk.Frame(
            conversation, style="Surface.TFrame", padding=(14, 12)
        )
        composer.grid(row=5, column=0, sticky="ew")
        composer.columnconfigure(0, weight=1)

        self.message_var = tk.StringVar()
        self.message_entry = ttk.Entry(
            composer,
            state="disabled",
            textvariable=self.message_var,
            style="Modern.TEntry",
            font=FONT_BODY,
        )
        self.message_entry.bind("<Return>", self._on_send)
        self.message_entry.grid(row=0, column=0, sticky="ew")

        self.send_button = ttk.Button(
            composer,
            text="Gửi",
            state="disabled",
            style="Primary.TButton",
            command=self._on_send,
        )
        self.send_button.grid(row=0, column=1, padx=(10, 0))

        self.file_button = ttk.Button(
            composer,
            text="Chọn file",
            command=self._choose_file,
            state="disabled",
            style="Secondary.TButton",
        )
        self.file_button.grid(row=0, column=2, padx=(8, 0))

        # --- TẦNG 3: THANH TRẠNG THÁI MẠNG PHÍA DƯỚI ---
        ttk.Frame(frame, style="Divider.TFrame", height=1).grid(
            row=3, column=0, sticky="ew"
        )
        notice_bar = ttk.Frame(frame, style="Notice.TFrame", padding=(16, 6))
        notice_bar.grid(row=4, column=0, sticky="ew")

        self.connection_notice_var = tk.StringVar(
            value="Chưa kết nối mạng."
        )
        ttk.Label(
            notice_bar,
            textvariable=self.connection_notice_var,
            style="Notice.TLabel",
            wraplength=960,
            justify="left",
        ).pack(anchor="w")

        self._init_chat_data()
        self._apply_theme()
        self._render_history()
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
        """Khởi tạo kho dữ liệu hội thoại rỗng; danh sách peer cập nhật từ UDP.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        self.current_chat: str | None = None

        self._peer_info: dict[str, dict] = {}
        self._peer_order: list[str] = []
        self._conversation_order: list[str] = []

        self._history = MessageHistory()
        self.chat_history = self._history.messages
        self._file_offers: dict[str, dict[str, dict]] = {}
        self.unread_count: dict[str, int] = {}
        self._chat_states: dict[str, str] = {}
        self._chat_reasons: dict[str, str] = {}
        self._drafts: dict[str, str] = {}

        self._peer_snapshot = None

        self.peer_list.delete(0, tk.END)
        self.conversation_list.delete(0, tk.END)

    def _format_status_badge(self, status: str) -> str:
        """Trả về ký hiệu ngắn gọn đại diện cho trạng thái của peer.

        Tham số đầu vào:
            status (str): Trạng thái của peer ("online", "away" hoặc khác).

        Giá trị trả về:
            str: Ký hiệu tròn trực quan ("●", "◐" hoặc "○").
        """
        if status == "online":
            return "●"
        if status == "away":
            return "◐"
        return "○"

    def _update_chat_header(self, username: str) -> None:
        """Cập nhật tiêu đề và dòng thông tin phụ của khung hội thoại đang mở.

        Tham số đầu vào:
            username (str): Username của peer đang xem.

        Giá trị trả về:
            None
        """
        info = self._peer_info[username]
        badge = self._format_status_badge(info["status"])
        self.chat_title_var.set(
            f"{info['display_name']}  {badge} {info['status']}"
        )
        if self._chat_subtitle_var is not None:
            endpoint = (
                f"{info['ip']}:{info['tcp_port']}"
                if info.get("ip") and info.get("tcp_port")
                else "chưa có địa chỉ TCP"
            )
            self._chat_subtitle_var.set(f"@{username} · {endpoint}")

    def _on_chat_selected(self, event: tk.Event) -> None:
        """Đọc dòng được chọn từ Listbox và mở cuộc hội thoại tương ứng.

        Tham số đầu vào:
            event (tk.Event): Sự kiện `<<ListboxSelect>>` từ Tkinter.

        Giá trị trả về:
            None
        """
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
        """Mở lịch sử của peer đã biết và khôi phục nội dung đang gõ dở.

        Tham số đầu vào:
            username (str): Username của peer cần mở hội thoại.

        Giá trị trả về:
            None
        """
        if self.current_chat is not None:
            self._drafts[self.current_chat] = self.message_var.get()
        self.current_chat = username
        self.message_var.set(self._drafts.get(username, ""))

        if username not in self._conversation_order:
            self._conversation_order.append(username)

        self._update_chat_header(username)
        self._render_history()

        self.unread_count[username] = 0
        self._refresh_conversation_list()
        self._update_chat_controls()

    def _render_history(self) -> None:
        """Vẽ lại lịch sử hội thoại theo dạng bong bóng trái/phải rồi khóa chỉnh sửa.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None

        Cách hoạt động:
            Xóa nội dung cũ của `history_text`, sau đó chèn từng tin nhắn với
            tag `self_sender`/`self_bubble` (nếu sender là `"Bạn"`) hoặc
            `peer_sender`/`peer_bubble` (nếu là đối phương). Nếu chưa có tin
            nhắn nào thì hiển thị gợi ý nhẹ ở giữa khung chat.
        """
        if self.history_text is None:
            return
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", tk.END)

        if self.current_chat is None:
            self.history_text.insert(
                tk.END,
                "Chọn một người dùng trong mạng LAN để bắt đầu trò chuyện.",
                "empty_hint",
            )
        else:
            messages = self.chat_history.get(self.current_chat, [])
            if not messages:
                self.history_text.insert(
                    tk.END,
                    "Chưa có tin nhắn nào trong cuộc trò chuyện này.",
                    "empty_hint",
                )
            else:
                for sender, text in messages:
                    if sender == "Bạn":
                        self.history_text.insert(
                            tk.END, "Bạn\n", "self_sender"
                        )
                        self.history_text.insert(
                            tk.END, f" {text} \n", "self_bubble"
                        )
                    else:
                        self.history_text.insert(
                            tk.END, f"{sender}\n", "peer_sender"
                        )
                        self.history_text.insert(
                            tk.END, f" {text} \n", "peer_bubble"
                        )
                    self.history_text.insert(tk.END, "\n", "spacer")

        self.history_text.configure(state="disabled")
        self.history_text.see(tk.END)

    def _receive_message(
        self,
        username: str,
        text: str,
    ) -> None:
        """Lưu tin nhắn đến vào hội thoại và cập nhật số tin chưa đọc.

        Tham số đầu vào:
            username (str): Username của người gửi.
            text (str): Nội dung tin nhắn UTF-8.

        Giá trị trả về:
            None

        Lưu ý:
            Chỉ được gọi trên luồng chính của Tkinter thông qua `_drain_network_events`.
        """
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
        """Vẽ lại danh sách hội thoại gần đây kèm số tin chưa đọc và trạng thái lời mời.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        selected = self.conversation_list.curselection()

        self.conversation_list.delete(0, tk.END)

        for username in self._conversation_order:
            info = self._peer_info[username]
            name = info["display_name"]
            badge = self._format_status_badge(info["status"])
            count = self.unread_count[username]

            label = f" {badge} {name} ({count})" if count else f" {badge} {name}"
            state = self._chat_states.get(username)
            if state == "incoming":
                label += " · Lời mời"
            elif state in ("connecting", "waiting", "accepting"):
                label += " · Đang chờ"
            if offers := self._file_offers.get(username):
                label += f" · {len(offers)} file chờ nhận"
            self.conversation_list.insert(tk.END, label)

        # Giữ nguyên dòng đang chọn sau khi vẽ lại danh sách.
        if selected:
            self.conversation_list.selection_set(selected[0])

    def _refresh_online_peers(self) -> None:
        """Lấy snapshot peer từ DiscoveryService và cập nhật Sidebar trên luồng UI.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
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

            if self._peer_count_var is not None:
                self._peer_count_var.set(
                    f"NGƯỜI DÙNG TRONG LAN ({len(peers)})"
                )

            self.peer_list.delete(0, tk.END)

            for peer in peers:
                badge = self._format_status_badge(peer.status)
                self.peer_list.insert(
                    tk.END,
                    f" {badge} {peer.display_name} (@{peer.username})"
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
                self._update_chat_header(self.current_chat)

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
        """Đổi trạng thái online/away qua DiscoveryService và cập nhật chấm màu.

        Tham số đầu vào:
            event (tk.Event | None): Sự kiện chọn combobox (tùy chọn).

        Giá trị trả về:
            None
        """
        if self.discovery is None or self.profile is None:
            return

        new_status = self.status_var.get()

        try:
            self.discovery.set_status(new_status)

        except ValueError:
            # Khôi phục lựa chọn về trạng thái hợp lệ của hồ sơ.
            self.status_var.set(self.profile.status)
            self._refresh_status_dot()

            self.connection_notice_var.set(
                "Trạng thái chỉ được là online hoặc away."
            )
            return

        self._refresh_status_dot()
        self.connection_notice_var.set(
            f"Đã đặt trạng thái: {new_status}. "
            "Sẽ phát trong gói UDP tiếp theo."
        )

    def _presence_notification(self, peers: list[Peer]) -> str:
        """Tạo chuỗi thông báo khi có peer xuất hiện hoặc rời mạng.

        Tham số đầu vào:
            peers (list[Peer]): Danh sách peer mới nhất từ `DiscoveryService`.

        Giá trị trả về:
            str: Nội dung thông báo, hoặc chuỗi rỗng nếu đã tắt thông báo.
        """
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
        """Hiển thị cổng TCP đang lắng nghe và số peer trên thanh trạng thái.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        if self.profile is None:
            return

        self.connection_notice_var.set(
            f"UDP đang chạy · TCP port: {self.profile.tcp_port}"
            f" · {len(self._peer_order)} peer hiện diện."
        )

    def _on_notifications_toggled(self) -> None:
        """Cập nhật lại thanh trạng thái ngay khi bật/tắt thông báo presence.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        self._show_network_summary()

    def post_network_event(
        self, event_type: str, username: str, data: dict | str = "",
    ) -> None:
        """Đẩy sự kiện từ luồng worker mạng vào hàng đợi thread-safe của UI.

        Tham số đầu vào:
            event_type (str): Loại sự kiện ("chat_state", "message", "sent",
                "send_failed", "network_error").
            username (str): Username liên quan đến sự kiện.
            data (dict | str): Dữ liệu đính kèm sự kiện.

        Giá trị trả về:
            None
        """
        with self._network_event_lock:
            if not self._closing.is_set():
                payload = data if isinstance(data, dict) else {"text": data}
                self._network_events.put((event_type, username, payload))

    def _remember_chat_peer(self, username: str, data: dict) -> None:
        """Ghi nhận peer từ kết nối TCP kể cả khi lượt cập nhật UDP chưa tới.

        Tham số đầu vào:
            username (str): Username của peer.
            data (dict): Thông tin đính kèm (`display_name`, `ip`, `tcp_port`).

        Giá trị trả về:
            None
        """
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
        """Rút và xử lý tối đa 50 sự kiện mạng mỗi lượt trên luồng chính Tkinter.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        self._events_poll_id = None
        if self._closing.is_set():
            return
        refresh_history = False
        for _ in range(50):
            try:
                event_type, username, data = self._network_events.get_nowait()
            except queue.Empty:
                break

            if event_type == "chat_state":
                self._remember_chat_peer(username, data)
                self._chat_states[username] = data["state"]
                self._chat_reasons[username] = data.get("reason", "")
                if data["state"] in ("disconnected", "expired", "declined", "error"):
                    self._file_offers.pop(username, None)
                    self._history.interrupt_files(username)
                    refresh_history |= username == self.current_chat
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

            elif event_type.startswith("file_"):
                self._handle_file_event(event_type, username, data)
                refresh_history |= username == self.current_chat

            elif event_type == "network_error":
                self.connection_notice_var.set(
                    f"Không thể nhận kết nối mới: {data['reason']}"
                )

        if refresh_history:
            self._render_history()
        self._events_poll_id = self.root.after(
            100, self._drain_network_events,
        )

    def _update_chat_controls(self) -> None:
        """Ẩn/hiện banner lời mời và bật/tắt vùng soạn tin theo trạng thái phiên.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        username = self.current_chat
        state = self._chat_states.get(username, "idle")
        for button in (
            self.invite_button, self.accept_button, self.decline_button,
        ):
            button.pack_forget()

        ready = state == "ready"
        self.message_entry.configure(state="normal" if ready else "disabled")
        self.send_button.configure(state="normal" if ready else "disabled")
        self.file_button.configure(state="normal" if ready else "disabled")
        if ready:
            offers = self._file_offers.get(username)
            if offers:
                offer = next(iter(offers.values()))
                self.invitation_var.set(f"{username} muốn gửi {offer['name']} ({offer['size']:,} byte).")
                self.invitation_frame.grid()
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

    def _choose_file(self) -> None:
        """Chọn một file và gửi lời mời cho peer đang trò chuyện."""
        username = self.current_chat
        if self.chat_network is None or self._chat_states.get(username) != "ready":
            return
        choice = filedialog.askopenfilename(parent=self.root, title=f"Chọn file để gửi cho {username}")
        if not choice or username != self.current_chat or self._closing.is_set():
            return
        try:
            self.chat_network.offer_file(username, Path(choice), background=True)
        except RuntimeError as error:
            self.connection_notice_var.set(str(error))
            return
        self.connection_notice_var.set(f"Đang chuẩn bị {Path(choice).name} cho {username}…")

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
        """Gửi lời mời trò chuyện tới peer đang chọn qua endpoint từ DiscoveryService.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
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
        """Đồng ý lời mời trò chuyện của hội thoại đang mở.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        if self.current_chat is not None and self.chat_network is not None:
            if self._file_offers.get(self.current_chat) and self._chat_states.get(self.current_chat) == "ready":
                self._reply_file(True)
            else:
                self.chat_network.accept_chat(self.current_chat)

    def _on_decline_chat(self) -> None:
        """Từ chối lời mời trò chuyện mà không xóa lịch sử hội thoại cũ.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        if self.current_chat is not None and self.chat_network is not None:
            if self._file_offers.get(self.current_chat) and self._chat_states.get(self.current_chat) == "ready":
                self._reply_file(False)
            else:
                self.chat_network.decline_chat(self.current_chat)

    def _on_send(self, event: tk.Event | None = None) -> str:
        """Gửi tin nhắn qua writer nền; chỉ ghi lịch sử khi nhận sự kiện `sent`.

        Tham số đầu vào:
            event (tk.Event | None): Sự kiện nhấn phím Return (tùy chọn).

        Giá trị trả về:
            str: Luôn trả về `"break"` để chặn hành vi mặc định của phím Enter.
        """
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
        """Chạy vòng lặp sự kiện Tkinter cho tới khi người dùng đóng cửa sổ.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            None
        """
        self.root.mainloop()


if __name__ == "__main__":
    app = ChatWindow()
    app.run()
