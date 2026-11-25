"""Form nhập hồ sơ trước khi kết nối."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk


def build_profile_form(
    root: tk.Tk, username_var: tk.StringVar, display_name_var: tk.StringVar,
    job_title_var: tk.StringVar, notice_var: tk.StringVar, on_start: Callable[[], None],
) -> ttk.Frame:
    """Dựng form, chuyển thao tác Bắt đầu cho cửa sổ và trả về frame để đóng."""
    root.geometry("520x520")
    root.minsize(440, 520)

    # Khung chứa ngoài cùng với nền Slate
    outer_frame = ttk.Frame(root, padding=24)
    outer_frame.pack(fill="both", expand=True)

    # Khung thẻ trắng (White Card) nổi bật ở giữa
    card = tk.Frame(
        outer_frame,
        bg="#ffffff",
        bd=1,
        relief="solid",
        highlightthickness=0,
    )
    card.pack(fill="both", expand=True, padx=12, pady=12)

    # Khung nội dung bên trong card
    inner = ttk.Frame(card, style="Card.TFrame", padding=24)
    inner.pack(fill="both", expand=True)
    inner.columnconfigure(1, weight=1)

    # Header của form đăng nhập
    logo_label = ttk.Label(
        inner,
        text="💬",
        font=("Segoe UI Emoji", 28),
        style="Card.TLabel",
    )
    logo_label.grid(row=0, column=0, columnspan=2, pady=(0, 2))

    title_label = ttk.Label(
        inner,
        text="LAN Chat P2P",
        font=("Segoe UI", 16, "bold"),
        foreground="#1e1b4b",
        style="Card.TLabel",
    )
    title_label.grid(row=1, column=0, columnspan=2, pady=(0, 2))

    sub_label = ttk.Label(
        inner,
        text="Đăng nhập hồ sơ để tham gia mạng nội bộ",
        font=("Segoe UI", 9),
        foreground="#64748b",
        style="Card.TLabel",
    )
    sub_label.grid(row=2, column=0, columnspan=2, pady=(0, 20))

    # Trường nhập Username
    ttk.Label(
        inner,
        text="Username:",
        font=("Segoe UI", 10, "bold"),
        style="Card.TLabel",
    ).grid(row=3, column=0, sticky="w", padx=(0, 12), pady=8)

    username_entry = ttk.Entry(
        inner,
        textvariable=username_var,
        style="Modern.TEntry",
    )
    username_entry.grid(row=3, column=1, sticky="ew", pady=8)

    # Trường nhập Tên hiển thị
    ttk.Label(
        inner,
        text="Tên hiển thị:",
        font=("Segoe UI", 10),
        style="Card.TLabel",
    ).grid(row=4, column=0, sticky="w", padx=(0, 12), pady=8)

    display_name_entry = ttk.Entry(
        inner,
        textvariable=display_name_var,
        style="Modern.TEntry",
    )
    display_name_entry.grid(row=4, column=1, sticky="ew", pady=8)

    # Trường nhập Chức danh
    ttk.Label(
        inner,
        text="Chức danh:",
        font=("Segoe UI", 10),
        style="Card.TLabel",
    ).grid(row=5, column=0, sticky="w", padx=(0, 12), pady=8)

    job_title_entry = ttk.Entry(
        inner,
        textvariable=job_title_var,
        style="Modern.TEntry",
    )
    job_title_entry.grid(row=5, column=1, sticky="ew", pady=8)

    # Nút Bắt đầu kết nối
    start_button = ttk.Button(
        inner,
        text="Bắt đầu kết nối",
        style="Primary.TButton",
        command=on_start,
    )
    start_button.grid(row=6, column=0, columnspan=2, pady=(20, 10), sticky="ew")

    # Dòng thông báo / lỗi đăng nhập
    notice_label = ttk.Label(
        inner,
        textvariable=notice_var,
        foreground="#ef4444",
        wraplength=340,
        justify="center",
        style="Card.TLabel",
        font=("Segoe UI", 9),
    )
    notice_label.grid(row=7, column=0, columnspan=2, pady=(4, 0))

    # Hỗ trợ bấm Enter từ các ô nhập để bắt đầu
    username_entry.bind("<Return>", lambda e: on_start())
    display_name_entry.bind("<Return>", lambda e: on_start())
    job_title_entry.bind("<Return>", lambda e: on_start())

    username_entry.focus_set()
    return outer_frame
