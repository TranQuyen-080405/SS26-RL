"""Rounded state chips and instance index badges."""

import re
import tkinter as tk

from Ui_app.ui_scale import font, px

_BADGE_BG = "#ffffff"
_BADGE_FG = "#1e1e2e"
_CONTAINER_BG = "#eceff4"
_INSTANCE_TAIL_RE = re.compile(r" #(\d+)$")


def chip_container_bg():
    return _CONTAINER_BG


def chip_radius():
    return px(6)


def badge_radius():
    return px(3)


def split_reward_display(display):
    s = str(display or "")
    m = _INSTANCE_TAIL_RE.search(s)
    if m:
        return s[: m.start()], int(m.group(1))
    return s, None


def _widget_bg(widget, fallback="#eceff4"):
    try:
        return widget.cget("bg")
    except tk.TclError:
        return fallback


def draw_round_rect(canvas, x1, y1, x2, y2, radius, fill, outline=None):
    if outline is None:
        outline = fill
    if x2 <= x1 or y2 <= y1:
        return
    r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    if r < 1:
        canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, tags="round_bg")
        return
    canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, fill=fill, outline=outline, style="pieslice", tags="round_bg")
    canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, fill=fill, outline=outline, style="pieslice", tags="round_bg")
    canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, fill=fill, outline=outline, style="pieslice", tags="round_bg")
    canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, fill=fill, outline=outline, style="pieslice", tags="round_bg")
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=outline, tags="round_bg")
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=outline, tags="round_bg")


class RoundedBlock(tk.Frame):
    """Khối bo góc nhẹ; đặt nội dung trong .inner."""

    def __init__(self, parent, bg, radius=None, canvas_bg=None, cursor=None, stretch_width=False, **kwargs):
        self._chip_bg = bg
        self._radius = chip_radius() if radius is None else radius
        self._canvas_bg = canvas_bg if canvas_bg is not None else _widget_bg(parent, _CONTAINER_BG)
        self._stretch_width = stretch_width
        self._last_w = 0
        self._last_h = 0
        self._sync_after_id = None
        self._in_sync = False
        self._bg_items = ()
        super().__init__(parent, bg=self._canvas_bg, **kwargs)
        if cursor:
            self.configure(cursor=cursor)
        self.canvas = tk.Canvas(self, bg=self._canvas_bg, highlightthickness=0, bd=0, cursor=cursor)
        self.canvas.pack()
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor=tk.NW)
        self.inner.bind("<Configure>", self._queue_sync)
        if stretch_width:
            self.bind("<Configure>", self._queue_sync)
        if cursor:
            self.inner.configure(cursor=cursor)
        self.after_idle(self._queue_sync)

    def _queue_sync(self, _event=None):
        if self._in_sync:
            return
        if self._sync_after_id is not None:
            return
        self._sync_after_id = self.after(20, self._sync_layout)

    def _sync_layout(self):
        self._sync_after_id = None
        if not self.winfo_exists():
            return
        self._in_sync = True
        try:
            req_w = max(1, self.inner.winfo_reqwidth())
            req_h = max(1, self.inner.winfo_reqheight())
            if self._stretch_width:
                try:
                    outer_w = max(req_w, self.winfo_width())
                except tk.TclError:
                    outer_w = req_w
                target_w = max(1, outer_w)
            else:
                target_w = req_w
            target_h = req_h
            if abs(target_w - self._last_w) < 2 and abs(target_h - self._last_h) < 2:
                return
            self._last_w = target_w
            self._last_h = target_h
            self.canvas.configure(width=target_w, height=target_h)
            self._redraw()
        except tk.TclError:
            pass
        finally:
            self._in_sync = False

    def _redraw(self):
        w = self._last_w or max(1, self.canvas.winfo_width())
        h = self._last_h or max(1, self.canvas.winfo_height())
        # Reuse canvas items to avoid flicker when many chips update.
        if not self._bg_items:
            draw_round_rect(self.canvas, 0, 0, w, h, self._radius, self._chip_bg, self._chip_bg)
            self._bg_items = tuple(self.canvas.find_withtag("round_bg"))
        else:
            self.canvas.delete("round_bg")
            draw_round_rect(self.canvas, 0, 0, w, h, self._radius, self._chip_bg, self._chip_bg)
            self._bg_items = tuple(self.canvas.find_withtag("round_bg"))
        self.canvas.tag_lower("round_bg")
        self.canvas.coords(self._win, 0, 0)

    def bind_chip_events(self, sequence, handler, add=False):
        for w in (self, self.canvas, self.inner):
            w.bind(sequence, handler, add="+" if add else None)

    def destroy(self):
        if self._sync_after_id is not None:
            try:
                self.after_cancel(self._sync_after_id)
            except tk.TclError:
                pass
            self._sync_after_id = None
        super().destroy()


def create_instance_badge(parent, idx, bg_behind, font_size=8):
    """Ô vuông trắng bo góc nhẹ, số ở giữa."""
    size = max(px(16), 16)
    wrap = tk.Frame(parent, bg=bg_behind)
    c = tk.Canvas(wrap, width=size, height=size, bg=bg_behind, highlightthickness=0, bd=0)
    c.pack()
    pad = 1
    draw_round_rect(c, pad, pad, size - pad, size - pad, badge_radius(), _BADGE_BG, _BADGE_BG)
    c.create_text(
        size // 2,
        size // 2,
        text=str(idx),
        fill=_BADGE_FG,
        font=font(font_size, weight="bold"),
    )
    return wrap


def build_reward_title(parent, title, idx, bg, fg, font_size=9, bold=True):
    """Tiêu đề block + badge số (nếu có)."""
    row = tk.Frame(parent, bg=bg)
    wt = "bold" if bold else "normal"
    lbl = tk.Label(row, text=title, bg=bg, fg=fg, font=font(font_size, weight=wt), anchor=tk.W)
    lbl.pack(side=tk.LEFT)
    if idx is not None:
        create_instance_badge(row, idx, bg, font_size=max(7, font_size - 1)).pack(side=tk.LEFT, padx=(px(5), 0))
    return row, lbl


def measure_instance_badge_width():
    return max(px(16), 16) + px(5)


def set_rounded_block_bg(block, bg, fg=None):
    """Đổi màu chip RoundedBlock (kéo thả / làm mờ)."""
    block._chip_bg = bg
    try:
        block.inner.configure(bg=bg)
    except tk.TclError:
        pass
    for child in block.inner.winfo_children():
        if fg is not None:
            _set_widget_bg_fg_tree(child, bg, fg)
        else:
            _set_widget_bg_tree(child, bg)
    try:
        block._redraw()
    except (AttributeError, tk.TclError):
        pass


def _set_widget_bg_fg_tree(widget, bg, fg):
    try:
        if isinstance(widget, tk.Label):
            widget.configure(bg=bg, fg=fg)
        elif isinstance(widget, tk.Frame):
            widget.configure(bg=bg)
            for child in widget.winfo_children():
                _set_widget_bg_fg_tree(child, bg, fg)
        elif isinstance(widget, tk.Canvas):
            widget.configure(bg=bg)
    except tk.TclError:
        pass


def make_formula_chip(parent, bg, surround_bg=None, cursor=None):
    """Chip bo góc trong thanh công thức (không lồng canvas ngoài)."""
    return RoundedBlock(
        parent,
        bg=bg,
        canvas_bg=surround_bg if surround_bg is not None else _widget_bg(parent, _BAR_FALLBACK),
        cursor=cursor or "hand2",
    )


_BAR_FALLBACK = "#313244"
_BAR_BG = "#313244"


def make_result_chip(parent, label, bg, fg, surround_bg, font_obj):
    """Chip bo góc nhỏ cho panel Check State."""
    block = RoundedBlock(parent, bg=bg, canvas_bg=surround_bg)
    base, idx = split_reward_display(label)
    title_row, title_lbl = build_reward_title(
        block.inner,
        base,
        idx,
        bg,
        fg,
        font_size=9,
        bold=True,
    )
    title_row.pack(padx=px(4), pady=px(2))
    try:
        title_lbl.configure(font=font_obj)
    except tk.TclError:
        pass
    block.pack(side=tk.LEFT, padx=(0, px(4)))
    return block


def make_flat_chip(parent, bg, surround_bg=None, cursor=None):
    """Chip phẳng (không canvas lồng) — legacy fallback."""
    surround_bg = surround_bg if surround_bg is not None else _widget_bg(parent, _BAR_BG)
    wrap = tk.Frame(parent, bg=surround_bg, bd=0)
    body = tk.Frame(wrap, bg=bg, bd=0, cursor=cursor or "")
    body.pack(padx=px(1), pady=px(1))
    wrap._chip_body = body
    wrap._chip_bg = bg
    wrap._surround_bg = surround_bg
    if cursor:
        wrap.configure(cursor=cursor)
    return wrap, body


def set_flat_chip_bg(chip_wrap, bg):
    chip_wrap._chip_bg = bg
    chip_wrap._chip_body.configure(bg=bg)
    for child in chip_wrap._chip_body.winfo_children():
        _set_widget_bg_tree(child, bg)


def _set_widget_bg_tree(widget, bg):
    try:
        if isinstance(widget, tk.Label):
            widget.configure(bg=bg)
        elif isinstance(widget, tk.Frame):
            widget.configure(bg=bg)
            for child in widget.winfo_children():
                _set_widget_bg_tree(child, bg)
        elif isinstance(widget, tk.Canvas):
            widget.configure(bg=bg)
    except tk.TclError:
        pass


def make_palette_chip(parent, label, bg, fg, active_bg, font_obj, on_press, on_motion, canvas_bg=None):
    block = RoundedBlock(
        parent,
        bg=bg,
        canvas_bg=canvas_bg or _widget_bg(parent, _CONTAINER_BG),
        cursor="hand2",
    )
    lbl = tk.Label(block.inner, text=label, bg=bg, fg=fg, font=font_obj, cursor="hand2", padx=px(6), pady=px(2))
    lbl.pack()
    block._active_bg = active_bg

    def _press(event, l=label):
        on_press(event, l)

    for w in (block, block.canvas, block.inner, lbl):
        w.bind("<ButtonPress-1>", _press)
        w.bind("<B1-Motion>", on_motion)
    block._label = lbl
    block._palette_label = label
    return block
