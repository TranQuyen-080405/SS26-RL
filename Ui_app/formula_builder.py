"""Ghép công thức reward — kéo thả, kéo từ palette, xóa từng cục."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from RL_lib.lab_registry import REWARD_ELEMENTS
from RL_lib.student_formula import parse_expr_to_tokens, tokens_to_expr

# Màu chip reward theo state module
_MODULE_CHIP = {
    "step": {"bg": "#94e2d5", "fg": "#11111b", "active": "#7dd3c0"},
    "obstacle": {"bg": "#f38ba8", "fg": "#11111b", "active": "#eba0ac"},
    "goal": {"bg": "#89b4fa", "fg": "#11111b", "active": "#74a8fc"},
    "checkpoint": {"bg": "#fab387", "fg": "#11111b", "active": "#f5a876"},
    "rotation": {"bg": "#cba6f7", "fg": "#11111b", "active": "#b794f6"},
    "explore_penalty": {"bg": "#f9e2af", "fg": "#1e1e2e", "active": "#f5d87a"},
}
_DEFAULT_REWARD = {"bg": "#b4befe", "fg": "#11111b", "active": "#a6b4f4"}

_OP_CHIP = {
    "+": {"bg": "#a6e3a1", "fg": "#1e1e2e"},
    "-": {"bg": "#eba0ac", "fg": "#1e1e2e"},
    "*": {"bg": "#89dceb", "fg": "#1e1e2e"},
    "/": {"bg": "#f5c2e7", "fg": "#1e1e2e"},
    "(": {"bg": "#9399b2", "fg": "#eff1f5"},
    ")": {"bg": "#9399b2", "fg": "#eff1f5"},
}
_DEFAULT_OP = {"bg": "#585b70", "fg": "#cdd6f4"}

_CHIP_NUM = {"bg": "#74c7ec", "fg": "#11111b"}
_BAR_BG = "#313244"
_DROP_LINE_CORE = "#ffffff"
_DROP_LINE_GLOW = "#89b4fa"
_GHOST_ALPHA = 0.88

_LABEL_MODULE = {meta["label"]: meta["module"] for meta in REWARD_ELEMENTS.values()}

_DRAG_THRESHOLD = 6
_INNER_PAD = 4


class FormulaBuilder(ttk.Frame):
    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self._tokens = []
        self._known_labels = []
        self._chip_frames = []
        self._drag = None
        self._ghost = None
        self._bar_outer = None
        self._palette_btns = []
        self._palette_built_w = -1
        self._palette_font = tkfont.Font(family="TkDefaultFont", size=8, weight="bold")

        ttk.Label(
            self,
            text="Reward — kéo nút xuống công thức (tự xuống dòng khi hết chỗ):",
            font=("", 9, "bold"),
        ).pack(anchor=tk.W)

        self._pal_inner = tk.Frame(self, bg="#eceff4")
        self._pal_inner.pack(fill=tk.X, pady=(0, 4))
        self._pal_inner.bind("<Configure>", self._on_palette_frame_configure)

        ttk.Label(
            self,
            text="Công thức tổng — kéo reward/phép từ trên hoặc dưới lên; × góc phải để xóa:",
            font=("", 9, "bold"),
        ).pack(anchor=tk.W)

        bar_outer = ttk.Frame(self)
        bar_outer.pack(fill=tk.X, pady=4)
        self._bar_outer = bar_outer

        self._chip_canvas = tk.Canvas(
            bar_outer, height=44, bg=_BAR_BG, highlightthickness=1, highlightbackground="#45475a"
        )
        self._chip_canvas.configure(takefocus=True)
        self._chip_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._chip_inner = tk.Frame(self._chip_canvas, bg=_BAR_BG)
        self._chip_win = self._chip_canvas.create_window(
            (_INNER_PAD, _INNER_PAD), window=self._chip_inner, anchor=tk.NW
        )
        self._chip_inner.bind("<Configure>", self._on_inner_configure)
        self._chip_canvas.bind("<Configure>", self._on_canvas_configure)

        for w in (self._chip_canvas, self._chip_inner, bar_outer, self):
            w.bind("<BackSpace>", self._on_backspace)
            w.bind("<Delete>", self._on_backspace)
            w.bind("<Button-1>", self._focus_bar)

        btn_col = ttk.Frame(bar_outer)
        btn_col.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(btn_col, text="⌫", width=3, command=self.pop_token).pack(pady=1)
        ttk.Button(btn_col, text="Xóa hết", width=7, command=self.clear).pack(pady=1)

        op = ttk.Frame(self)
        op.pack(fill=tk.X, pady=2)
        ttk.Label(op, text="Phép — kéo lên công thức:", font=("", 8)).pack(side=tk.LEFT, padx=(0, 4))
        for sym, disp in (("+", "+"), ("-", "−"), ("*", "×"), ("/", "÷"), ("(", "("), (")", ")")):
            style = _OP_CHIP.get(sym, _DEFAULT_OP)
            btn = tk.Button(
                op,
                text=disp,
                width=3,
                bg=style["bg"],
                fg=style["fg"],
                activebackground=style["bg"],
                relief=tk.RAISED,
                bd=1,
                font=("", 9, "bold"),
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=1)
            btn.bind("<ButtonPress-1>", lambda e, s=sym: self._op_press(e, s))
            btn.bind("<B1-Motion>", self._palette_motion)

        num_row = ttk.Frame(self)
        num_row.pack(fill=tk.X, pady=2)
        self._num = tk.StringVar(value="1")
        ttk.Entry(num_row, textvariable=self._num, width=6).pack(side=tk.LEFT)
        ttk.Button(num_row, text="Thêm số", command=self._append_number).pack(side=tk.LEFT, padx=4)

        root = self.winfo_toplevel()
        root.bind("<B1-Motion>", self._global_motion, add="+")
        root.bind("<ButtonRelease-1>", self._global_release, add="+")

    def _reward_palette(self, label):
        module = _LABEL_MODULE.get(label, "step")
        return _MODULE_CHIP.get(module, _DEFAULT_REWARD)

    def _chip_style(self, token):
        kind = token["kind"]
        if kind == "reward":
            s = self._reward_palette(token["value"])
            return {"bg": s["bg"], "fg": s["fg"], "font": ("", 9, "bold")}, 8, 4
        if kind == "num":
            return {**_CHIP_NUM, "font": ("", 9, "bold")}, 6, 4
        sym = token["value"]
        s = _OP_CHIP.get(sym, _DEFAULT_OP)
        return {"bg": s["bg"], "fg": s["fg"], "font": ("", 10, "bold")}, 5, 4

    def _token_for_label(self, label):
        return {"kind": "reward", "value": label, "display": label}

    def _token_for_op(self, sym):
        return {
            "kind": "op",
            "value": sym,
            "display": {"+": "+", "-": "−", "*": "×", "/": "÷"}.get(sym, sym),
        }

    def _on_palette_frame_configure(self, event):
        w = event.width
        if w <= 1 or w == self._palette_built_w:
            return
        self._rebuild_palette(w)

    def _make_palette_button(self, parent, lbl):
        pal = self._reward_palette(lbl)
        btn = tk.Button(
            parent,
            text=lbl,
            bg=pal["bg"],
            fg=pal["fg"],
            activebackground=pal["active"],
            relief=tk.RAISED,
            bd=2,
            padx=6,
            pady=2,
            font=("", 8, "bold"),
            cursor="hand2",
        )
        btn.bind("<ButtonPress-1>", lambda e, l=lbl: self._palette_press(e, l))
        btn.bind("<B1-Motion>", self._palette_motion)
        return btn

    def _measure_palette_btn(self, lbl):
        return self._palette_font.measure(lbl) + 20

    def _rebuild_palette(self, width=None):
        if width is None:
            width = self._pal_inner.winfo_width()
        if width <= 1:
            return
        if width == self._palette_built_w and self._palette_btns:
            return
        self._palette_built_w = width

        for w in self._pal_inner.winfo_children():
            w.destroy()
        self._palette_btns = []

        if not self._known_labels:
            return

        row = None
        row_w = 0
        gap = 4
        for lbl in self._known_labels:
            bw = self._measure_palette_btn(lbl)
            if row is None or (row_w > 0 and row_w + gap + bw > width):
                row = tk.Frame(self._pal_inner, bg="#eceff4")
                row.pack(fill=tk.X, anchor=tk.W)
                row_w = 0
            btn = self._make_palette_button(row, lbl)
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self._palette_btns.append(btn)
            row_w += (gap if row_w > 0 else 0) + bw + 4

    def _focus_bar(self, _event=None):
        if self._drag and self._drag.get("active"):
            return
        self._chip_canvas.focus_set()

    def _on_inner_configure(self, event):
        if self._drag and self._drag.get("active"):
            self._refresh_drop_visual(self._drag.get("insert_idx", 0))

    def _on_canvas_configure(self, event):
        self._chip_canvas.itemconfigure(self._chip_win, width=max(event.width - 8, 4))

    def _on_backspace(self, event):
        self.pop_token()
        return "break"

    def set_labels(self, labels):
        self._known_labels = list(labels)
        self._palette_built_w = -1
        self.update_idletasks()
        w = self._pal_inner.winfo_width()
        if w <= 1:
            w = self.winfo_width()
        if w > 1:
            self._rebuild_palette(w)

    def get_tokens(self):
        return list(self._tokens)

    def get_expr(self):
        return tokens_to_expr(self._tokens)

    def set_expr(self, expr):
        self._tokens = parse_expr_to_tokens(expr, self._known_labels)
        self._redraw_chips()

    def set_tokens(self, tokens):
        self._tokens = list(tokens)
        self._redraw_chips()

    def insert_token(self, token, index=None):
        if index is None or index < 0:
            index = len(self._tokens)
        if index > len(self._tokens):
            index = len(self._tokens)
        self._tokens.insert(index, dict(token))
        self._redraw_chips()
        self._notify()

    def append_reward(self, label):
        self.insert_token(self._token_for_label(label))

    def append_op(self, sym):
        self.insert_token(self._token_for_op(sym))

    def append_num(self, num):
        self.insert_token({"kind": "num", "value": str(num), "display": str(num)})

    def _append_number(self):
        raw = self._num.get().strip()
        if raw:
            self.append_num(raw)

    def remove_token_at(self, index):
        if 0 <= index < len(self._tokens):
            self._tokens.pop(index)
            self._redraw_chips()
            self._notify()

    def pop_token(self):
        if self._tokens:
            self._tokens.pop()
            self._redraw_chips()
            self._notify()

    def clear(self):
        self._tokens = []
        self._redraw_chips()
        self._notify()

    def _move_token(self, from_idx, to_idx):
        if from_idx < 0 or from_idx >= len(self._tokens):
            return
        if to_idx < 0:
            to_idx = 0
        if to_idx > len(self._tokens):
            to_idx = len(self._tokens)
        if from_idx == to_idx or from_idx + 1 == to_idx:
            return
        item = self._tokens.pop(from_idx)
        if to_idx > from_idx:
            to_idx -= 1
        self._tokens.insert(to_idx, item)

    def _drop_index(self, x_root):
        if not self._chip_frames:
            return 0
        for i, w in enumerate(self._chip_frames):
            if not w.winfo_exists():
                continue
            x1 = w.winfo_rootx()
            x2 = x1 + w.winfo_width()
            if x_root < (x1 + x2) // 2:
                return i
        return len(self._chip_frames)

    def _is_over_formula_bar(self, x_root, y_root):
        target = self._bar_outer if self._bar_outer and self._bar_outer.winfo_exists() else self._chip_canvas
        if not target.winfo_exists():
            return False
        x1 = target.winfo_rootx()
        y1 = target.winfo_rooty()
        x2 = x1 + target.winfo_width()
        y2 = y1 + target.winfo_height()
        return x1 <= x_root <= x2 and y1 <= y_root <= y2

    def _insert_x_canvas(self, insert_idx):
        """Tọa độ X trên canvas cho vạch chèn."""
        if not self._chip_frames:
            return _INNER_PAD + 8
        if insert_idx <= 0:
            w = self._chip_frames[0]
            return _INNER_PAD + max(w.winfo_x() - 3, 2)
        if insert_idx >= len(self._chip_frames):
            w = self._chip_frames[-1]
            return _INNER_PAD + w.winfo_x() + w.winfo_width() + 3
        w = self._chip_frames[insert_idx]
        return _INNER_PAD + max(w.winfo_x() - 3, 2)

    def _hide_drop_visual(self):
        self._chip_canvas.delete("drop_indicator")
        try:
            self._chip_canvas.tag_raise(self._chip_win)
        except tk.TclError:
            pass

    def _refresh_drop_visual(self, insert_idx):
        self._hide_drop_visual()
        if insert_idx is None:
            return
        try:
            self._chip_canvas.tag_lower(self._chip_win)
        except tk.TclError:
            pass
        canvas_h = max(self._chip_canvas.winfo_height(), 44)
        x = self._insert_x_canvas(insert_idx)
        y1, y2 = 2, canvas_h - 2
        self._chip_canvas.create_line(
            x, y1, x, y2, fill=_DROP_LINE_GLOW, width=9, tags="drop_indicator", capstyle=tk.ROUND
        )
        self._chip_canvas.create_line(
            x, y1, x, y2, fill=_DROP_LINE_CORE, width=3, tags="drop_indicator", capstyle=tk.ROUND
        )
        self._chip_canvas.create_polygon(
            x, y1, x - 5, y1 + 8, x + 5, y1 + 8,
            fill=_DROP_LINE_CORE, outline=_DROP_LINE_GLOW, tags="drop_indicator",
        )
        self._chip_canvas.create_polygon(
            x, y2, x - 5, y2 - 8, x + 5, y2 - 8,
            fill=_DROP_LINE_CORE, outline=_DROP_LINE_GLOW, tags="drop_indicator",
        )

    def _show_ghost(self, event, token):
        self._hide_ghost()
        style, padx, pady = self._chip_style(token)
        self._ghost = tk.Toplevel(self)
        self._ghost.overrideredirect(True)
        try:
            self._ghost.attributes("-alpha", _GHOST_ALPHA)
        except tk.TclError:
            pass
        self._ghost.attributes("-topmost", True)
        lbl = tk.Label(
            self._ghost,
            text=" %s " % token["display"],
            bg=style["bg"],
            fg=style["fg"],
            font=style["font"],
            relief=tk.RIDGE,
            bd=3,
            padx=padx,
            pady=pady,
        )
        lbl.pack()
        self._move_ghost(event)

    def _move_ghost(self, event):
        if self._ghost and self._ghost.winfo_exists():
            self._ghost.geometry("+%d+%d" % (event.x_root + 12, event.y_root + 12))

    def _hide_ghost(self):
        if self._ghost and self._ghost.winfo_exists():
            self._ghost.destroy()
        self._ghost = None

    def _start_drag_active(self, event):
        if not self._drag or self._drag.get("active"):
            return
        self._drag["active"] = True
        token = self._drag.get("token")
        if token:
            self._show_ghost(event, token)
        mode = self._drag.get("mode")
        if mode == "reorder":
            idx = self._drag["from"]
            if 0 <= idx < len(self._chip_frames):
                fr = self._chip_frames[idx]
                fr.configure(bg="#45475a")
                for child in fr.winfo_children():
                    if not getattr(child, "_is_del_btn", False):
                        child.configure(fg="#6c7086", bg="#45475a")
        elif mode in ("new", "new_op") and self._drag.get("source_btn"):
            try:
                self._drag["source_btn"].configure(relief=tk.SUNKEN)
            except tk.TclError:
                pass

    def _update_drag(self, event):
        if not self._drag:
            return
        dx = abs(event.x_root - self._drag["x0"])
        dy = abs(event.y_root - self._drag["y0"])
        if not self._drag.get("active") and max(dx, dy) >= _DRAG_THRESHOLD:
            self._start_drag_active(event)
        if not self._drag.get("active"):
            return
        self._move_ghost(event)
        if self._is_over_formula_bar(event.x_root, event.y_root):
            insert_at = self._drop_index(event.x_root)
            self._drag["insert_idx"] = insert_at
            self._refresh_drop_visual(insert_at)
            self._chip_canvas.configure(highlightbackground="#f38ba8")
        else:
            self._drag["insert_idx"] = None
            self._hide_drop_visual()
            self._chip_canvas.configure(highlightbackground="#45475a")

    def _finish_drag(self, event):
        if not self._drag:
            return
        drag = self._drag
        self._drag = None
        self._hide_ghost()
        self._hide_drop_visual()
        self._chip_canvas.configure(highlightbackground="#45475a")
        source_btn = drag.get("source_btn")
        if source_btn and source_btn.winfo_exists():
            try:
                source_btn.configure(relief=tk.RAISED)
            except tk.TclError:
                pass

        if not drag.get("active"):
            src = drag.get("source_btn")
            if drag.get("mode") == "new" and drag.get("label"):
                if src is None or event.widget is src:
                    self.append_reward(drag["label"])
            elif drag.get("mode") == "new_op" and drag.get("op_sym"):
                if src is None or event.widget is src:
                    self.append_op(drag["op_sym"])
            elif drag.get("mode") == "reorder":
                self._chip_canvas.focus_set()
            return

        if not self._is_over_formula_bar(event.x_root, event.y_root):
            self._redraw_chips()
            return

        to_idx = self._drop_index(event.x_root)
        if drag["mode"] in ("new", "new_op"):
            self.insert_token(drag["token"], to_idx)
        elif drag["mode"] == "reorder":
            self._move_token(drag["from"], to_idx)
            self._redraw_chips()
            self._notify()

    def _palette_press(self, event, label):
        self._drag = {
            "mode": "new",
            "from": None,
            "label": label,
            "op_sym": None,
            "token": self._token_for_label(label),
            "source_btn": event.widget,
            "x0": event.x_root,
            "y0": event.y_root,
            "active": False,
            "insert_idx": None,
        }

    def _op_press(self, event, sym):
        self._drag = {
            "mode": "new_op",
            "from": None,
            "label": None,
            "op_sym": sym,
            "token": self._token_for_op(sym),
            "source_btn": event.widget,
            "x0": event.x_root,
            "y0": event.y_root,
            "active": False,
            "insert_idx": None,
        }

    def _palette_motion(self, event):
        self._update_drag(event)

    def _chip_press(self, event, index):
        if getattr(event.widget, "_is_del_btn", False):
            return
        self._drag = {
            "mode": "reorder",
            "from": index,
            "label": None,
            "token": self._tokens[index],
            "x0": event.x_root,
            "y0": event.y_root,
            "active": False,
            "insert_idx": None,
            "widget": event.widget,
        }

    def _chip_motion(self, event):
        self._update_drag(event)

    def _global_motion(self, event):
        self._update_drag(event)

    def _global_release(self, event):
        if not self._drag:
            return
        drag = self._drag
        if not drag.get("active") and drag.get("mode") in ("new", "new_op"):
            src = drag.get("source_btn")
            if src is not None and event.widget is not src:
                self._finish_drag_silent()
                return
        self._finish_drag(event)

    def _delete_token_at(self, index):
        self.remove_token_at(index)

    def _on_delete_click(self, event, index):
        self._delete_token_at(index)
        return "break"

    def _bind_chip_drag(self, chip, index):
        chip.bind("<ButtonPress-1>", lambda e, i=index: self._chip_press(e, i))
        chip.bind("<B1-Motion>", self._chip_motion)

    def _make_chip_frame(self, index, token):
        style, padx, pady = self._chip_style(token)
        bg = style["bg"]
        outer = tk.Frame(self._chip_inner, bg=bg, relief=tk.RAISED, bd=2, cursor="hand2")
        outer.pack(side=tk.LEFT, padx=2, pady=4)

        chip = tk.Label(
            outer,
            text=" %s " % token["display"],
            bg=bg,
            fg=style["fg"],
            font=style["font"],
            bd=0,
            padx=padx + 4,
            pady=pady + 2,
            cursor="hand2",
        )
        chip.pack()

        del_btn = tk.Label(
            outer,
            text="×",
            bg="#1e1e2e",
            fg="#9399b2",
            font=("", 6, "bold"),
            cursor="hand2",
            padx=2,
            pady=0,
        )
        del_btn._is_del_btn = True
        del_btn.place(relx=1.0, rely=0.0, anchor=tk.NE, x=-1, y=1)
        del_btn.bind("<Button-1>", lambda e, i=index: self._on_delete_click(e, i))
        del_btn.bind("<Enter>", lambda e, w=del_btn: w.configure(bg="#f38ba8", fg="#1e1e2e"))
        del_btn.bind("<Leave>", lambda e, w=del_btn: w.configure(bg="#1e1e2e", fg="#9399b2"))

        self._chip_frames.append(outer)
        self._bind_chip_drag(chip, index)
        return outer

    def _redraw_chips(self):
        self._finish_drag_silent()
        self._chip_frames = []
        for w in self._chip_inner.winfo_children():
            w.destroy()
        if not self._tokens:
            hint = tk.Label(
                self._chip_inner,
                text="  Kéo reward/phép lên đây hoặc bấm để thêm…  ",
                bg=_BAR_BG,
                fg="#6c7086",
                font=("", 9, "italic"),
            )
            hint.pack(side=tk.LEFT, padx=2, pady=4)
            hint.bind("<BackSpace>", self._on_backspace)
            hint.bind("<Button-1>", self._focus_bar)
            return

        for i, t in enumerate(self._tokens):
            self._make_chip_frame(i, t)

    def _finish_drag_silent(self):
        if self._drag and self._drag.get("source_btn"):
            btn = self._drag["source_btn"]
            if btn.winfo_exists():
                try:
                    btn.configure(relief=tk.RAISED)
                except tk.TclError:
                    pass
        self._drag = None
        self._hide_ghost()
        self._hide_drop_visual()

    def is_dragging(self):
        return self._drag is not None

    def _notify(self):
        if self.on_change:
            self.on_change()
