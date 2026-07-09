"""Widget UI dạng hộp — dễ nhìn, dễ bấm cho người mới."""

import tkinter as tk
from tkinter import ttk

from Ui_app.ui_scale import font, px

BOX_ON = "[✓]"
BOX_OFF = "[ ]"

_BTN_STYLES = {
    "primary": ("#a6e3a1", "#11111b", "#7fd87a"),
    "danger": ("#f38ba8", "#11111b", "#e06c8a"),
    "secondary": ("#585b70", "#cdd6f4", "#6c7086"),
    "accent": ("#89b4fa", "#11111b", "#7aaef8"),
}


def box_button(parent, text, command=None, role="secondary", **kwargs):
    """Nút nền màu, viền nổi — thay ttk.Button mỏng."""
    bg, fg, active = _BTN_STYLES.get(role, _BTN_STYLES["secondary"])
    opts = dict(
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=active,
        activeforeground=fg,
        relief=tk.RAISED,
        bd=1,
        padx=px(5),
        pady=px(2),
        cursor="hand2",
        font=font(10, weight="bold" if role in ("primary", "danger") else "normal"),
    )
    opts.update(kwargs)
    return tk.Button(parent, **opts)


class SegmentGroup:
    """Nhóm chọn dạng nút hộp (thay radio tròn). options: [(label, value), ...]."""

    def __init__(self, parent, variable, options, command=None, padx=3, uniform_width=False):
        self.frame = ttk.Frame(parent)
        self.variable = variable
        self.command = command
        self._uniform_width = uniform_width
        self._buttons = []
        _padx = px(padx)
        btn_width = max((len(label) for label, _ in options), default=0) if uniform_width else None
        for label, value in options:
            btn = tk.Button(
                self.frame,
                text=label,
                relief=tk.RAISED,
                bd=1,
                padx=px(5),
                pady=px(2),
                cursor="hand2",
                font=font(10),
                width=btn_width,
                command=lambda v=value: self._select(v),
            )
            btn.pack(side=tk.LEFT, padx=_padx)
            self._buttons.append((btn, value))
        variable.trace_add("write", lambda *_: self._paint())
        self._paint()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def _select(self, value):
        self.variable.set(value)
        if self.command:
            self.command()

    def _paint(self):
        cur = self.variable.get()
        for btn, value in self._buttons:
            if value == cur:
                btn.configure(
                    relief=tk.SUNKEN,
                    bg="#89b4fa",
                    fg="#11111b",
                    font=font(10, weight="bold" if not self._uniform_width else "normal"),
                )
            else:
                btn.configure(
                    relief=tk.RAISED,
                    bg="#45475a",
                    fg="#cdd6f4",
                    font=font(10),
                )

    def set_enabled(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        for btn, _ in self._buttons:
            btn.configure(state=state)
        if enabled:
            self._paint()


    def refresh_scale(self):
        for btn, _ in self._buttons:
            btn.configure(padx=px(5), pady=px(2))
        self._paint()


def setup_train_tree_boxes(tree):
    """Cột chọn map train — ô vuông [✓] / [ ] thay vì tick tròn."""
    tree.heading("on", text="Chọn")
    tree.column("on", width=px(48), anchor=tk.CENTER, stretch=False)
    tree.tag_configure("map_on", foreground="#a6e3a1")
    tree.tag_configure("map_off", foreground="#9399b2")
    tree.tag_configure("row_a", background="#2a2a3c")
    tree.tag_configure("row_b", background="#313244")
    tree.tag_configure("drag_over", background="#45475a")


def style_train_treeview(tree, root):
    """Hàng cao hơn, heading đậm — bảng dễ đọc."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Train.Treeview", rowheight=px(28), font=font(9, family="Segoe UI"))
    style.configure("Train.Treeview.Heading", font=font(10, family="Segoe UI", weight="bold"), padding=(px(5), px(3)))
    style.map(
        "Train.Treeview",
        background=[("selected", "#585b70")],
        foreground=[("selected", "#cdd6f4")],
    )
    tree.configure(style="Train.Treeview")
    setup_train_tree_boxes(tree)


def train_map_mark(enabled):
    return BOX_ON if enabled else BOX_OFF


def train_row_tags(enabled, index):
    state = "map_on" if enabled else "map_off"
    stripe = "row_a" if index % 2 else "row_b"
    return (state, stripe)
