"""Hệ thống thiết kế màu sắc, phông chữ và style ttk cho LAN Chat.

Module này tập trung toàn bộ token giao diện (Light Mode và Dark Mode) theo tinh
thần thống nhất của taste-skill: một hệ thống màu rõ tương phản, không dùng tông
tím/lavender, phân cấp chữ mạch lạc và đồng bộ trên mọi widget Tkinter/ttk.
"""

from dataclasses import dataclass
import ctypes
import sys
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class ThemePalette:
    """Bộ token màu bất biến cho một chế độ giao diện (Light hoặc Dark).

    Mục đích và trách nhiệm:
        Lưu trữ toàn bộ mã màu của nền, bề mặt, chữ, viền, nút bấm, bong bóng
        tin nhắn và màu trạng thái mạng để mọi thành phần UI dùng chung một
        nguồn chân lý duy nhất.

    Tham số đầu vào:
        name (str): Tên chế độ giao diện ("light" hoặc "dark").
        bg_app (str): Màu nền chính của cửa sổ ứng dụng.
        bg_surface (str): Màu nền thẻ nội dung, khung chat và vùng nhập liệu.
        bg_sidebar (str): Màu nền thanh bên chứa danh sách peer và hội thoại.
        bg_subtle (str): Màu nền nhẹ cho banner lời mời hoặc vùng nhấn phụ.
        bg_input (str): Màu nền của ô nhập văn bản và danh sách.
        bg_input_disabled (str): Màu nền ô nhập khi đang bị khóa.
        bg_hover (str): Màu nền khi rê chuột vào nút phụ hoặc mục danh sách.
        bg_selected (str): Màu nền của dòng đang được chọn trong Listbox.
        border (str): Màu viền mảnh phân tách các vùng nội dung.
        border_focus (str): Màu viền khi ô nhập đang được focus.
        text_primary (str): Màu chữ chính, độ tương phản cao.
        text_secondary (str): Màu chữ phụ (chức danh, trạng thái, thông tin mạng).
        text_muted (str): Màu chữ mờ cho thành phần bị khóa hoặc gợi ý.
        accent (str): Màu nhấn chính cho nút hành động quan trọng.
        accent_hover (str): Màu nhấn chính khi rê chuột.
        accent_pressed (str): Màu nhấn chính khi nhấn giữ.
        accent_text (str): Màu chữ đặt trên nền màu nhấn chính.
        danger (str): Màu nhấn cảnh báo/từ chối lời mời.
        danger_hover (str): Màu cảnh báo khi rê chuột.
        danger_text (str): Màu chữ trên nút cảnh báo.
        status_online (str): Màu chỉ báo trạng thái online.
        status_away (str): Màu chỉ báo trạng thái away.
        status_offline (str): Màu chỉ báo trạng thái offline.
        bubble_self_bg (str): Màu nền tin nhắn do chính người dùng gửi.
        bubble_self_fg (str): Màu chữ tin nhắn do chính người dùng gửi.
        bubble_peer_bg (str): Màu nền tin nhắn nhận từ đối phương.
        bubble_peer_fg (str): Màu chữ tin nhắn nhận từ đối phương.
        notice_bg (str): Màu nền thanh trạng thái mạng phía dưới.
        notice_fg (str): Màu chữ thanh trạng thái mạng phía dưới.

    Giá trị trả về:
        ThemePalette: Đối tượng dữ liệu bất biến (frozen dataclass).

    Lưu ý:
        Sử dụng `frozen=True` để tránh vô tình sửa đổi bảng màu trong lúc chạy.
    """

    name: str
    bg_app: str
    bg_surface: str
    bg_sidebar: str
    bg_subtle: str
    bg_input: str
    bg_input_disabled: str
    bg_hover: str
    bg_selected: str
    border: str
    border_focus: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    danger: str
    danger_hover: str
    danger_text: str
    status_online: str
    status_away: str
    status_offline: str
    bubble_self_bg: str
    bubble_self_fg: str
    bubble_peer_bg: str
    bubble_peer_fg: str
    notice_bg: str
    notice_fg: str


# Bảng màu Light Mode: nền trắng ngà tinh gọn, chữ than đậm, màu nhấn xanh dương kỹ thuật.
LIGHT_THEME = ThemePalette(
    name="light",
    bg_app="#F4F6F8",
    bg_surface="#FFFFFF",
    bg_sidebar="#EDF1F5",
    bg_subtle="#E8F1FD",
    bg_input="#FFFFFF",
    bg_input_disabled="#F1F3F5",
    bg_hover="#E2E8F0",
    bg_selected="#D6E6FC",
    border="#D5DCE4",
    border_focus="#0F62FE",
    text_primary="#111827",
    text_secondary="#4B5563",
    text_muted="#8A94A6",
    accent="#0F62FE",
    accent_hover="#0353E9",
    accent_pressed="#0043CE",
    accent_text="#FFFFFF",
    danger="#DC2626",
    danger_hover="#B91C1C",
    danger_text="#FFFFFF",
    status_online="#16A34A",
    status_away="#D97706",
    status_offline="#6B7280",
    bubble_self_bg="#0F62FE",
    bubble_self_fg="#FFFFFF",
    bubble_peer_bg="#EEF2F6",
    bubble_peer_fg="#111827",
    notice_bg="#E8EDF3",
    notice_fg="#374151",
)


# Bảng màu Dark Mode: nền than chì sâu kiểu ứng dụng kỹ thuật, chữ sáng dịu, màu nhấn xanh lam.
DARK_THEME = ThemePalette(
    name="dark",
    bg_app="#0E1318",
    bg_surface="#151C24",
    bg_sidebar="#11171E",
    bg_subtle="#1A283A",
    bg_input="#1B242E",
    bg_input_disabled="#141A22",
    bg_hover="#24303D",
    bg_selected="#1E3A5F",
    border="#263240",
    border_focus="#3B82F6",
    text_primary="#F1F5F9",
    text_secondary="#94A3B8",
    text_muted="#64748B",
    accent="#2563EB",
    accent_hover="#3B82F6",
    accent_pressed="#1D4ED8",
    accent_text="#FFFFFF",
    danger="#EF4444",
    danger_hover="#DC2626",
    danger_text="#FFFFFF",
    status_online="#22C55E",
    status_away="#F59E0B",
    status_offline="#64748B",
    bubble_self_bg="#2563EB",
    bubble_self_fg="#F8FAFC",
    bubble_peer_bg="#1E293B",
    bubble_peer_fg="#E2E8F0",
    notice_bg="#0B0F14",
    notice_fg="#94A3B8",
)


# Thang phông chữ thống nhất cho toàn bộ ứng dụng (ưu tiên Segoe UI trên Windows).
FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 16, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 10)
FONT_HEADING = (FONT_FAMILY, 11, "bold")
FONT_SECTION = (FONT_FAMILY, 9, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_BODY_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_MONO = ("Consolas", 9)


class ThemeManager:
    """Quản lý trạng thái Light/Dark Mode và áp dụng style đồng bộ cho ttk.

    Mục đích và trách nhiệm:
        - Giữ trạng thái theme hiện tại ("light" hoặc "dark").
        - Chuyển đổi qua lại giữa hai theme khi người dùng bấm nút toggle.
        - Cấu hình toàn bộ style chuẩn của `ttk.Style` theo bảng màu đang chọn.

    Tham số đầu vào:
        initial_mode (str): Chế độ khởi tạo, nhận "light" hoặc "dark".
            Mặc định là "light".

    Ngoại lệ:
        ValueError: Nếu `initial_mode` không phải "light" hoặc "dark".
    """

    _THEMES: dict[str, ThemePalette] = {
        "light": LIGHT_THEME,
        "dark": DARK_THEME,
    }

    def __init__(self, initial_mode: str = "light") -> None:
        """Khởi tạo ThemeManager với chế độ màu ban đầu hợp lệ.

        Tham số đầu vào:
            initial_mode (str): Tên chế độ ban đầu ("light" hoặc "dark").

        Giá trị trả về:
            None

        Ngoại lệ:
            ValueError: Nếu truyền vào tên chế độ không được hỗ trợ.
        """
        if initial_mode not in self._THEMES:
            raise ValueError(
                f"Chế độ giao diện không hợp lệ: {initial_mode}. "
                "Chỉ hỗ trợ 'light' hoặc 'dark'."
            )
        self._mode: str = initial_mode

    @property
    def mode(self) -> str:
        """Trả về tên chế độ giao diện hiện tại.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            str: "light" hoặc "dark".
        """
        return self._mode

    @property
    def palette(self) -> ThemePalette:
        """Trả về bảng màu ThemePalette tương ứng với chế độ hiện tại.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            ThemePalette: Bảng màu đang được kích hoạt.
        """
        return self._THEMES[self._mode]

    @property
    def toggle_label(self) -> str:
        """Trả về nhãn hiển thị cho nút chuyển đổi Sáng/Tối.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            str: Nhãn chỉ rõ chế độ sẽ chuyển sang khi người dùng bấm nút.
        """
        return "Chế độ tối" if self._mode == "light" else "Chế độ sáng"

    def set_mode(self, mode: str) -> ThemePalette:
        """Đặt chế độ giao diện sang "light" hoặc "dark".

        Tham số đầu vào:
            mode (str): Tên chế độ mới ("light" hoặc "dark").

        Giá trị trả về:
            ThemePalette: Bảng màu sau khi cập nhật.

        Ngoại lệ:
            ValueError: Nếu `mode` không hợp lệ.
        """
        if mode not in self._THEMES:
            raise ValueError(
                f"Chế độ giao diện không hợp lệ: {mode}. "
                "Chỉ hỗ trợ 'light' hoặc 'dark'."
            )
        self._mode = mode
        return self.palette

    def toggle(self) -> ThemePalette:
        """Đảo qua lại giữa Light Mode và Dark Mode.

        Tham số đầu vào:
            Không có.

        Giá trị trả về:
            ThemePalette: Bảng màu mới sau khi chuyển đổi.
        """
        next_mode = "dark" if self._mode == "light" else "light"
        return self.set_mode(next_mode)

    def apply_ttk_styles(self, root: tk.Tk) -> ttk.Style:
        """Áp dụng bảng màu hiện tại cho cửa sổ gốc và toàn bộ widget ttk.

        Tham số đầu vào:
            root (tk.Tk): Cửa sổ Tkinter gốc của ứng dụng.

        Giá trị trả về:
            ttk.Style: Đối tượng Style đã được cấu hình theo bảng màu hiện tại.

        Cách hoạt động:
            1. Chuyển ttk sang theme nền "clam" để Windows không khóa màu nền
               của nút bấm, ô nhập và combobox.
            2. Cấu hình màu nền cửa sổ `root` và option cho popup danh sách của
               Combobox.
            3. Đăng ký các nhóm style có tên rõ ràng: Frame, Label, Button
               (Primary/Secondary/Danger), Entry, Combobox, Checkbutton.
        """
        p = self.palette
        style = ttk.Style(root)

        # Dùng theme 'clam' vì theme mặc định trên Windows ('vista') bỏ qua
        # nhiều thuộc tính background/fieldbackground của ttk.Button và Entry.
        if "clam" in style.theme_names():
            style.theme_use("clam")

        root.configure(bg=p.bg_app)

        # Đồng bộ màu danh sách thả xuống (popdown listbox) của ttk.Combobox.
        root.option_add("*TCombobox*Listbox.background", p.bg_input)
        root.option_add("*TCombobox*Listbox.foreground", p.text_primary)
        root.option_add("*TCombobox*Listbox.selectBackground", p.accent)
        root.option_add("*TCombobox*Listbox.selectForeground", p.accent_text)
        root.option_add("*TCombobox*Listbox.font", FONT_BODY)

        # 1. Khung chứa (Frames)
        style.configure("App.TFrame", background=p.bg_app)
        style.configure("Surface.TFrame", background=p.bg_surface)
        style.configure("Sidebar.TFrame", background=p.bg_sidebar)
        style.configure("Banner.TFrame", background=p.bg_subtle)
        style.configure("Notice.TFrame", background=p.notice_bg)
        style.configure(
            "Card.TFrame",
            background=p.bg_surface,
            borderwidth=1,
            relief="solid",
        )
        style.configure("Divider.TFrame", background=p.border)

        # 2. Nhãn chữ (Labels)
        style.configure(
            "App.TLabel",
            background=p.bg_app,
            foreground=p.text_primary,
            font=FONT_BODY,
        )
        style.configure(
            "Surface.TLabel",
            background=p.bg_surface,
            foreground=p.text_primary,
            font=FONT_BODY,
        )
        style.configure(
            "Title.TLabel",
            background=p.bg_surface,
            foreground=p.text_primary,
            font=FONT_TITLE,
        )
        style.configure(
            "Subtitle.TLabel",
            background=p.bg_surface,
            foreground=p.text_secondary,
            font=FONT_SUBTITLE,
        )
        style.configure(
            "Heading.TLabel",
            background=p.bg_surface,
            foreground=p.text_primary,
            font=FONT_HEADING,
        )
        style.configure(
            "Header.TLabel",
            background=p.bg_app,
            foreground=p.text_primary,
            font=FONT_HEADING,
        )
        style.configure(
            "HeaderMuted.TLabel",
            background=p.bg_app,
            foreground=p.text_secondary,
            font=FONT_SMALL,
        )
        style.configure(
            "Section.TLabel",
            background=p.bg_sidebar,
            foreground=p.text_secondary,
            font=FONT_SECTION,
        )
        style.configure(
            "Banner.TLabel",
            background=p.bg_subtle,
            foreground=p.text_primary,
            font=FONT_BODY,
        )
        style.configure(
            "Error.TLabel",
            background=p.bg_surface,
            foreground=p.danger,
            font=FONT_SMALL,
        )
        style.configure(
            "Notice.TLabel",
            background=p.notice_bg,
            foreground=p.notice_fg,
            font=FONT_SMALL,
        )

        # 3. Nút bấm chính (Primary): dùng cho hành động quan trọng nhất.
        style.configure(
            "Primary.TButton",
            background=p.accent,
            foreground=p.accent_text,
            bordercolor=p.accent,
            lightcolor=p.accent,
            darkcolor=p.accent,
            focuscolor=p.accent_text,
            font=FONT_BODY_BOLD,
            padding=(14, 7),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Primary.TButton",
            background=[
                ("disabled", p.bg_hover),
                ("pressed", p.accent_pressed),
                ("active", p.accent_hover),
            ],
            foreground=[
                ("disabled", p.text_muted),
                ("active", p.accent_text),
            ],
        )

        # 4. Nút bấm phụ (Secondary): dùng cho thao tác hỗ trợ (đổi theme, chọn file...).
        style.configure(
            "Secondary.TButton",
            background=p.bg_surface,
            foreground=p.text_primary,
            bordercolor=p.border,
            lightcolor=p.bg_surface,
            darkcolor=p.bg_surface,
            focuscolor=p.border_focus,
            font=FONT_BODY,
            padding=(12, 6),
            borderwidth=1,
            relief="solid",
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("disabled", p.bg_input_disabled),
                ("pressed", p.bg_selected),
                ("active", p.bg_hover),
            ],
            foreground=[
                ("disabled", p.text_muted),
                ("active", p.text_primary),
            ],
            bordercolor=[
                ("disabled", p.border),
                ("active", p.border_focus),
            ],
        )

        # 5. Nút cảnh báo (Danger): dùng cho hành động từ chối lời mời.
        style.configure(
            "Danger.TButton",
            background=p.danger,
            foreground=p.danger_text,
            bordercolor=p.danger,
            lightcolor=p.danger,
            darkcolor=p.danger,
            focuscolor=p.danger_text,
            font=FONT_BODY_BOLD,
            padding=(12, 6),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Danger.TButton",
            background=[
                ("disabled", p.bg_hover),
                ("active", p.danger_hover),
            ],
            foreground=[
                ("disabled", p.text_muted),
                ("active", p.danger_text),
            ],
        )

        # 6. Ô nhập liệu (Entry)
        style.configure(
            "Modern.TEntry",
            fieldbackground=p.bg_input,
            foreground=p.text_primary,
            insertcolor=p.text_primary,
            bordercolor=p.border,
            lightcolor=p.border,
            darkcolor=p.border,
            padding=(10, 7),
            borderwidth=1,
            relief="solid",
        )
        style.map(
            "Modern.TEntry",
            fieldbackground=[("disabled", p.bg_input_disabled)],
            foreground=[("disabled", p.text_muted)],
            bordercolor=[
                ("focus", p.border_focus),
                ("disabled", p.border),
            ],
        )

        # 7. Hộp chọn trạng thái (Combobox)
        style.configure(
            "Modern.TCombobox",
            fieldbackground=p.bg_input,
            background=p.bg_surface,
            foreground=p.text_primary,
            arrowcolor=p.text_secondary,
            bordercolor=p.border,
            lightcolor=p.border,
            darkcolor=p.border,
            padding=(8, 5),
            borderwidth=1,
            relief="solid",
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", p.bg_input)],
            foreground=[("readonly", p.text_primary)],
            selectbackground=[("readonly", p.bg_input)],
            selectforeground=[("readonly", p.text_primary)],
            bordercolor=[("focus", p.border_focus)],
        )

        # 8. Hộp kiểm (Checkbutton) trên thanh header
        style.configure(
            "Header.TCheckbutton",
            background=p.bg_app,
            foreground=p.text_secondary,
            indicatorcolor=p.bg_input,
            font=FONT_SMALL,
            padding=(4, 2),
        )
        style.map(
            "Header.TCheckbutton",
            background=[("active", p.bg_app)],
            foreground=[("active", p.text_primary)],
            indicatorcolor=[("selected", p.accent)],
        )

        return style

    def apply_window_chrome(self, root: tk.Tk) -> None:
        """Đồng bộ thanh tiêu đề và viền cửa sổ Windows theo Light/Dark Mode.

        Tham số đầu vào:
            root (tk.Tk): Cửa sổ Tkinter gốc cần cập nhật khung viền.

        Giá trị trả về:
            None

        Cách hoạt động:
            Sử dụng Windows DWM API (`DwmSetWindowAttribute`) qua thư viện chuẩn
            `ctypes` để đổi màu thanh tiêu đề (caption), chữ tiêu đề và viền cửa
            sổ theo bảng màu hiện tại, giữ nguyên khả năng resize, Snap và icon
            Taskbar của Windows. Tự bỏ qua an toàn nếu không chạy trên Windows.
        """
        if sys.platform != "win32" or not root.winfo_exists():
            return

        p = self.palette
        try:
            root.update_idletasks()
            # Trên Tkinter Windows, winfo_id() trả về HWND vùng nội dung;
            # GetParent() lấy đúng HWND của khung cửa sổ ngoài cùng.
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
            dwmapi = ctypes.windll.dwmapi

            # Bật/tắt chế độ tối cho thanh tiêu đề Windows (Win 10 1903+ & Win 11).
            is_dark = ctypes.c_int(1 if self._mode == "dark" else 0)
            for attr in (20, 19):
                dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(is_dark), ctypes.sizeof(is_dark)
                )

            # Đổi màu viền (34), màu nền thanh tiêu đề (35) và màu chữ (36) trên Win 11.
            color_attrs = (
                (34, _hex_to_colorref(p.border)),
                (35, _hex_to_colorref(p.bg_app)),
                (36, _hex_to_colorref(p.text_primary)),
            )
            for attr, colorref in color_attrs:
                value = ctypes.c_int(colorref)
                dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
        except (AttributeError, OSError, ValueError):
            # Không làm gián đoạn ứng dụng trên hệ điều hành không hỗ trợ DWM.
            return


def _hex_to_colorref(hex_color: str) -> int:
    """Chuyển mã màu hex `#RRGGBB` sang định dạng COLORREF (`0x00BBGGRR`) của Windows.

    Tham số đầu vào:
        hex_color (str): Chuỗi mã màu dạng `#RRGGBB`.

    Giá trị trả về:
        int: Số nguyên 24-bit theo thứ tự BGR dùng cho Win32 DWM API.
    """
    cleaned = hex_color.lstrip("#")
    r = int(cleaned[0:2], 16)
    g = int(cleaned[2:4], 16)
    b = int(cleaned[4:6], 16)
    return (b << 16) | (g << 8) | r


def create_app_icon(master: tk.Misc, accent_hex: str) -> tk.PhotoImage:
    """Tạo biểu tượng ứng dụng 24x24 gọn nhẹ trong bộ nhớ để thay icon mặc định của Tk.

    Tham số đầu vào:
        master (tk.Misc): Cửa sổ Tk sở hữu ảnh (bắt buộc truyền để hỗ trợ nhiều
            cửa sổ `tk.Tk()` độc lập trong kiểm thử hoặc chạy đa cửa sổ).
        accent_hex (str): Mã màu nhấn chính của ứng dụng (ví dụ `#0F62FE`).

    Giá trị trả về:
        tk.PhotoImage: Ảnh biểu tượng hình bong bóng chat tối giản.

    Lưu ý:
        Phải giữ tham chiếu đối tượng `PhotoImage` trả về (ví dụ `self._app_icon`)
        để bộ thu gom rác Python không xóa mất ảnh icon.
    """
    size = 24
    icon = tk.PhotoImage(master=master, width=size, height=size)

    # Vẽ nền hình vuông bo góc bằng màu nhấn chính.
    for y in range(2, size - 2):
        for x in range(2, size - 2):
            in_corner = (
                (x in (2, size - 3) and y in (2, size - 3))
                or (x in (2, size - 3) and y in (3, size - 4))
                or (x in (3, size - 4) and y in (2, size - 3))
            )
            if not in_corner:
                icon.put(accent_hex, (x, y))

    # Vẽ hai vạch trắng tối giản đại diện cho nội dung tin nhắn.
    for x in range(7, 17):
        icon.put("#FFFFFF", (x, 9))
        icon.put("#FFFFFF", (x, 10))
    for x in range(7, 14):
        icon.put("#FFFFFF", (x, 13))
        icon.put("#FFFFFF", (x, 14))

    return icon

