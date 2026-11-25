"""Bảng màu và kiểu widget dùng chung cho giao diện LAN Chat."""

import tkinter as tk
from tkinter import ttk


BACKGROUND = "#f3f6f4"
SURFACE = "#ffffff"
SIDEBAR = "#183b3b"
ACCENT = "#16796b"
TEXT = "#19352f"
MUTED = "#647970"
BORDER = "#dce6df"


def configure_styles(root: tk.Tk) -> ttk.Style:
    """Cấu hình theme ttk, font và trạng thái tương tác; trả bộ style của root."""
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=BACKGROUND)
    root.option_add("*Font", "{Segoe UI} 10")
    style.configure(".", font=("Segoe UI", 10), background=BACKGROUND, foreground=TEXT)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("Header.TFrame", background=SURFACE)
    style.configure("Sidebar.TFrame", background=SIDEBAR)
    style.configure("Footer.TFrame", background=BACKGROUND)
    style.configure("InviteCard.TFrame", background="#eaf3ef")
    style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
    style.configure("Card.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("Sidebar.TLabel", background=SIDEBAR, foreground="#eff7f2")
    style.configure("SectionTitle.TLabel", background=SIDEBAR,
                    foreground="#b8d6cd", font=("Segoe UI", 9, "bold"))
    style.configure("Invite.TLabel", background="#eaf3ef", foreground="#285b4d")
    style.configure("Notice.TLabel", background=BACKGROUND,
                    foreground=MUTED, font=("Segoe UI", 9))

    # Cùng kích thước thao tác cho cả các nút chính và nút phụ.
    style.configure("TButton", padding=(12, 8), relief="flat", borderwidth=0)
    for name, color, hover in (
        ("Primary", ACCENT, "#116456"),
        ("Success", "#28795b", "#1b6045"),
        ("Danger", "#ae4a45", "#923d38"),
    ):
        style.configure(f"{name}.TButton", background=color, foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=(14, 8),
                        borderwidth=0, relief="flat", focusthickness=2, focuscolor="#9cc5b6")
        style.map(f"{name}.TButton",
                  background=[("disabled", "#e3eae5"), ("pressed", hover), ("active", hover)],
                  foreground=[("disabled", "#8b9c92")])
    style.configure("Secondary.TButton", background="#eaf0ec", foreground="#345b4f",
                    font=("Segoe UI", 10), padding=(12, 8), borderwidth=0)
    style.map("Secondary.TButton", background=[("disabled", "#f0f3f0"), ("active", "#dce9e1")],
              foreground=[("disabled", "#8b9c92")])
    style.configure("Sidebar.TButton", background="#28504d", foreground="#e7f5ee",
                    padding=(6, 3), borderwidth=0, font=("Segoe UI", 13))
    style.map("Sidebar.TButton", background=[("active", "#376a61")],
              foreground=[("disabled", "#9cb6ab")])
    style.configure("Modern.TEntry", fieldbackground=SURFACE, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    padding=(10, 9), insertcolor=TEXT)
    style.map("Modern.TEntry", bordercolor=[("focus", ACCENT)],
              fieldbackground=[("disabled", "#f2f5f2")],
              foreground=[("disabled", "#8b9c92")])
    style.configure("TCheckbutton", background=SURFACE, foreground=MUTED,
                    font=("Segoe UI", 9), focuscolor=SURFACE)
    style.map("TCheckbutton", background=[("active", SURFACE)])
    style.configure("TCombobox", padding=(8, 5), arrowsize=12,
                    fieldbackground=SURFACE, background="#edf3ee", bordercolor=BORDER)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE)],
              foreground=[("readonly", TEXT)], selectbackground=[("readonly", SURFACE)],
              selectforeground=[("readonly", TEXT)])
    style.configure("TScrollbar", background="#c3d4c8", troughcolor=BACKGROUND,
                    bordercolor="#c3d4c8", lightcolor="#c3d4c8", darkcolor="#c3d4c8",
                    relief="flat", gripcount=0, borderwidth=0, arrowsize=11)
    style.map("TScrollbar", background=[("active", "#9cb6a7")])
    style.configure("Sidebar.Vertical.TScrollbar", background="#365a52", troughcolor=SIDEBAR,
                    bordercolor="#365a52", lightcolor="#365a52", darkcolor="#365a52",
                    arrowcolor="#b8d6cd", borderwidth=0, arrowsize=10)
    style.configure("Sidebar.Horizontal.TScrollbar", background="#365a52", troughcolor=SIDEBAR,
                    bordercolor="#365a52", lightcolor="#365a52", darkcolor="#365a52",
                    arrowcolor="#b8d6cd", borderwidth=0, arrowsize=10)
    for orientation, sticky in (("Vertical", "ns"), ("Horizontal", "ew")):
        style.layout(f"{orientation}.TScrollbar", [
            (f"{orientation}.Scrollbar.trough", {"sticky": sticky, "children": [
                (f"{orientation}.Scrollbar.thumb", {"expand": True, "sticky": "nsew"}),
            ]}),
        ])
    return style
