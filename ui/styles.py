"""Kiểu hiển thị ttk dùng chung cho cửa sổ LAN Chat."""

import tkinter as tk
from tkinter import ttk


def configure_styles(root: tk.Tk) -> ttk.Style:
    """Áp dụng theme của cửa sổ và trả về bộ style đã cấu hình."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Màu sắc chủ đạo (Design Tokens)
    bg_app = "#f8fafc"         # Nền tổng thể (Slate 50)
    bg_card = "#ffffff"        # Nền card / vùng làm việc chính
    bg_sidebar = "#f1f5f9"     # Nền thanh sidebar (Slate 100)
    border_color = "#e2e8f0"   # Màu viền tinh giản (Slate 200)
    primary_color = "#4f46e5"  # Màu nhấn Indigo chính
    primary_hover = "#4338ca"  # Màu hover Indigo
    text_primary = "#0f172a"   # Chữ chính (Slate 900)
    text_muted = "#64748b"     # Chữ phụ / ghi chú (Slate 500)
    success_color = "#10b981"  # Màu xanh thành công (Emerald 500)
    danger_color = "#ef4444"   # Màu đỏ cảnh báo / từ chối (Rose 500)

    # Thiết lập Frame & Label nền tảng
    style.configure("TFrame", background=bg_app)
    style.configure("Card.TFrame", background=bg_card, relief="flat")
    style.configure("Sidebar.TFrame", background=bg_sidebar)
    style.configure("Header.TFrame", background=bg_card)
    style.configure("Footer.TFrame", background=bg_sidebar)
    style.configure("InviteCard.TFrame", background="#eff6ff")

    style.configure(
        "TLabel",
        background=bg_app,
        foreground=text_primary,
        font=("Segoe UI", 10),
    )
    style.configure(
        "Card.TLabel",
        background=bg_card,
        foreground=text_primary,
        font=("Segoe UI", 10),
    )
    style.configure(
        "Sidebar.TLabel",
        background=bg_sidebar,
        foreground=text_primary,
        font=("Segoe UI", 10),
    )
    style.configure(
        "SectionTitle.TLabel",
        background=bg_sidebar,
        foreground="#334155",
        font=("Segoe UI", 9, "bold"),
    )
    style.configure(
        "Invite.TLabel",
        background="#eff6ff",
        foreground="#1e40af",
        font=("Segoe UI", 10),
    )
    style.configure(
        "Notice.TLabel",
        background=bg_sidebar,
        foreground=text_muted,
        font=("Segoe UI", 9),
    )

    # Style cho Nút bấm chính (Primary Button: Indigo)
    style.configure(
        "Primary.TButton",
        background=primary_color,
        foreground="#ffffff",
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
        padding=(12, 6),
    )
    style.map(
        "Primary.TButton",
        background=[("disabled", "#cbd5e1"), ("active", primary_hover)],
        foreground=[("disabled", "#94a3b8")],
    )

    # Style cho Nút thành công (Success Button: Green / Đồng ý)
    style.configure(
        "Success.TButton",
        background=success_color,
        foreground="#ffffff",
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
        padding=(12, 6),
    )
    style.map(
        "Success.TButton",
        background=[("disabled", "#cbd5e1"), ("active", "#059669")],
        foreground=[("disabled", "#94a3b8")],
    )

    # Style cho Nút cảnh báo (Danger Button: Red / Từ chối)
    style.configure(
        "Danger.TButton",
        background=danger_color,
        foreground="#ffffff",
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
        padding=(12, 6),
    )
    style.map(
        "Danger.TButton",
        background=[("disabled", "#cbd5e1"), ("active", "#dc2626")],
        foreground=[("disabled", "#94a3b8")],
    )

    # Style cho Nút phụ (Secondary Button: Slate outline)
    style.configure(
        "Secondary.TButton",
        background="#f1f5f9",
        foreground="#475569",
        font=("Segoe UI", 9),
        borderwidth=1,
        padding=(10, 5),
    )
    style.map(
        "Secondary.TButton",
        background=[("disabled", "#f8fafc"), ("active", "#e2e8f0")],
        foreground=[("disabled", "#cbd5e1")],
    )

    # Style cho ô nhập liệu (Entry)
    style.configure(
        "Modern.TEntry",
        fieldbackground="#ffffff",
        foreground=text_primary,
        padding=6,
        font=("Segoe UI", 10),
        borderwidth=1,
    )

    # Checkbutton & Combobox
    style.configure(
        "TCheckbutton",
        background=bg_card,
        foreground=text_primary,
        font=("Segoe UI", 9),
    )
    style.configure(
        "TCombobox",
        font=("Segoe UI", 9),
    )
    return style
