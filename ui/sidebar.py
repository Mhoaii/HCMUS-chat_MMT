"""Các danh sách người dùng và hội thoại trên thanh bên."""

from collections.abc import Callable, Iterable
import tkinter as tk
from tkinter import ttk


def build_sidebar(
    frame: ttk.Frame, on_reload: Callable[[], None],
) -> tuple[tk.Listbox, tk.Listbox, ttk.Button]:
    """Dựng hai danh sách và nút tải lại."""
    sidebar_container = tk.Frame(
        frame,
        bg="#f1f5f9",
        bd=0,
        highlightbackground="#e2e8f0",
        highlightthickness=1,
    )
    sidebar_container.grid(
        row=1, column=0, sticky="nsew", padx=(0, 0)
    )
    sidebar_container.columnconfigure(0, weight=1)
    sidebar_container.rowconfigure(0, weight=1)
    sidebar_container.rowconfigure(1, weight=1)

    # Mục 1: Người dùng LAN (Online Peers)
    peers_section = ttk.Frame(sidebar_container, style="Sidebar.TFrame", padding=(12, 12, 12, 6))
    peers_section.grid(row=0, column=0, sticky="nsew")

    peers_header = ttk.Frame(peers_section, style="Sidebar.TFrame")
    peers_header.pack(fill="x", pady=(0, 6))

    ttk.Label(
        peers_header,
        text="NGƯỜI DÙNG LAN",
        style="SectionTitle.TLabel",
    ).pack(side="left")

    reload_peers_button = ttk.Button(
        peers_header,
        text="↻",
        width=3,
        style="Secondary.TButton",
        command=on_reload,
    )
    reload_peers_button.pack(side="right")

    peer_list = _scrollable_list(peers_section)

    # Mục 2: Cuộc trò chuyện gần đây (Conversations)
    recent_section = ttk.Frame(sidebar_container, style="Sidebar.TFrame", padding=(12, 6, 12, 12))
    recent_section.grid(row=1, column=0, sticky="nsew")

    recent_header = ttk.Frame(recent_section, style="Sidebar.TFrame")
    recent_header.pack(fill="x", pady=(0, 6))

    ttk.Label(
        recent_header,
        text="CUỘC TRÒ CHUYỆN",
        style="SectionTitle.TLabel",
    ).pack(side="left")

    conversation_list = _scrollable_list(recent_section)
    return peer_list, conversation_list, reload_peers_button


def _scrollable_list(section: ttk.Frame) -> tk.Listbox:
    """Tạo danh sách có thanh cuộn ngang và dọc."""
    body = ttk.Frame(section, style="Sidebar.TFrame")
    body.pack(fill="both", expand=True)
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)
    items = tk.Listbox(
        body,
        width=26,
        height=6,
        exportselection=False,
        bg="#ffffff",
        fg="#1e293b",
        selectbackground="#e0e7ff",
        selectforeground="#1e1b4b",
        relief="flat",
        bd=0,
        highlightbackground="#cbd5e1",
        highlightthickness=1,
        highlightcolor="#6366f1",
        font=("Segoe UI", 10),
        activestyle="none",
    )
    items.grid(row=0, column=0, sticky="nsew")
    scroll_y = ttk.Scrollbar(
        body, orient="vertical", command=items.yview,
    )
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x = ttk.Scrollbar(
        body, orient="horizontal", command=items.xview,
    )
    scroll_x.grid(row=1, column=0, sticky="ew")
    items.configure(
        yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set,
    )
    return items


def replace_rows(widget: tk.Listbox, labels: Iterable[str], selected: int | None) -> None:
    """Cập nhật các dòng, khôi phục lựa chọn, bàn phím và vị trí cuộn."""
    y, x = widget.yview()[0], widget.xview()[0]
    widget.delete(0, tk.END)
    for label in labels:
        widget.insert(tk.END, label)
    if selected is not None:
        widget.selection_set(selected)
        widget.activate(selected)
        widget.selection_anchor(selected)
    widget.yview_moveto(y)
    widget.xview_moveto(x)
