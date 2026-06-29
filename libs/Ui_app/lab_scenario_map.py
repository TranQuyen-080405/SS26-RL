"""Map 12×5 tương tác — đặt robot, goal, CP, tường."""

import tkinter as tk
from tkinter import ttk

from RL_lib.grid import neighbor_xy, is_valid

CELL = 35
MARGIN = 8
_MAX_CANVAS_W = 450

_STATE_BG = "#eceff4"
_STATE_FG = "#1e1e2e"
_REWARD_BG = "#313244"
_REWARD_FG = "#cdd6f4"
_POS = "#a6e3a1"
_NEG = "#f38ba8"
_ZERO = "#9399b2"
_TOTAL_POS_BG = "#2d4a3e"
_TOTAL_NEG_BG = "#4a2d35"
_HINT_FG = "#6c7086"


class LabScenarioMap5:
    def __init__(self, parent, world, on_change=None):
        self.world = world
        self.on_change = on_change
        self.frame = ttk.LabelFrame(parent, text="Check State", padding=4)
        self.frame.pack(fill=tk.X)

        tools = ttk.Frame(self.frame)
        tools.pack(fill=tk.X, pady=(0, 4))
        self._tool = tk.StringVar(value="robot")
        for val, label in (
            ("robot", "Robot"),
            ("goal", "Goal"),
            ("cp", "Checkpoint"),
            ("wall", "Walls"),
        ):
            ttk.Radiobutton(tools, text=label, variable=self._tool, value=val).pack(side=tk.LEFT, padx=4)
        ttk.Button(tools, text="Reset map", command=self._reset).pack(side=tk.RIGHT, padx=4)

        map_wrap = ttk.Frame(self.frame)
        map_wrap.pack(fill=tk.X)
        xscroll = ttk.Scrollbar(map_wrap, orient=tk.HORIZONTAL)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas = tk.Canvas(
            map_wrap,
            bg="#1e1e2e",
            highlightthickness=0,
            cursor="crosshair",
            xscrollcommand=xscroll.set,
        )
        self.canvas.pack(side=tk.TOP, fill=tk.X)
        xscroll.config(command=self.canvas.xview)
        self.canvas.bind("<Button-1>", self._on_click)

        act_row = ttk.Frame(self.frame)
        act_row.pack(fill=tk.X, pady=(4, 4))
        ttk.Label(act_row, text="Move:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(act_row, text="Rotate Left", command=lambda: self._action("rotate left")).pack(side=tk.LEFT, padx=3)
        ttk.Button(act_row, text="Forward", command=lambda: self._action("forward")).pack(side=tk.LEFT, padx=3)
        ttk.Button(act_row, text="Rotate Right", command=lambda: self._action("rotate right")).pack(side=tk.LEFT, padx=3)

        self._build_result_panel()
        self.set_result_display(state_rows=[], has_action=False)

        self.redraw()

    def _build_result_panel(self):
        outer = ttk.Frame(self.frame)
        outer.pack(fill=tk.X, pady=(6, 0))

        self._state_box = tk.LabelFrame(
            outer, text=" STATE ", font=("", 9, "bold"), bg=_STATE_BG, fg=_STATE_FG, padx=8, pady=6
        )
        self._state_box.pack(fill=tk.X, pady=(0, 4))
        self._state_inner = tk.Frame(self._state_box, bg=_STATE_BG)
        self._state_inner.pack(fill=tk.X)

        self._reward_box = tk.LabelFrame(
            outer, text=" REWARD ", font=("", 9, "bold"), bg=_REWARD_BG, fg=_REWARD_FG, padx=8, pady=6
        )
        self._reward_box.pack(fill=tk.X)
        self._reward_inner = tk.Frame(self._reward_box, bg=_REWARD_BG)
        self._reward_inner.pack(fill=tk.X)

        self._action_lbl = tk.Label(
            self._reward_inner, text="", bg=_REWARD_BG, fg="#89b4fa", font=("", 9, "bold"), anchor=tk.W
        )
        self._action_lbl.pack(fill=tk.X, pady=(0, 4))

        self._total_frame = tk.Frame(self._reward_inner, bg=_REWARD_BG)
        self._total_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            self._total_frame, text="TỔNG", bg=_REWARD_BG, fg=_REWARD_FG, font=("", 10, "bold")
        ).pack(side=tk.LEFT, padx=(0, 8))
        self._total_val = tk.Label(
            self._total_frame, text="", font=("", 14, "bold"), padx=10, pady=4
        )
        self._total_val.pack(side=tk.LEFT)

        self._parts_frame = tk.Frame(self._reward_inner, bg=_REWARD_BG)
        self._parts_frame.pack(fill=tk.X)

        # self._hint_lbl = tk.Label(
        #     self._reward_inner,
        #     text="→ Bấm Forward / Rotate để xem điểm từng action",
        #     bg=_REWARD_BG,
        #     fg=_HINT_FG,
        #     font=("", 9, "italic"),
        #     anchor=tk.W,
        # )

    @staticmethod
    def _format_formula(formula):
        if not formula or not str(formula).strip():
            return "(trống — chưa cộng điểm)"
        return formula.replace(" + ", "\n  + ").replace(" - ", "\n  − ")

    def _clear_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def set_result_display(
        self,
        state_rows,
        has_action=False,
        action_name="",
        formula="",
        total=0.0,
        parts=None,
    ):
        """parts: [(label, chip_bg, chip_fg, value), ...]"""
        self._clear_frame(self._state_inner)
        parts = parts or []

        for text in state_rows:
            tk.Label(
                self._state_inner,
                text=text,
                bg=_STATE_BG,
                fg=_STATE_FG,
                font=("Consolas", 9),
                anchor=tk.W,
            ).pack(fill=tk.X, pady=1)

        if has_action:
            if hasattr(self, "_hint_lbl"):
                self._hint_lbl.pack_forget()
            act = action_name or "?"
            self._action_lbl.config(text="Action: %s" % act)
            self._action_lbl.pack(fill=tk.X, pady=(0, 4))

            no_formula = not (formula and str(formula).strip())
            sign = "+" if total >= 0 else ""
            total_text = "%s%.1f điểm" % (sign, total)
            if no_formula:
                tb, tf = "#45475a", _HINT_FG
            elif total > 0:
                tb, tf = _TOTAL_POS_BG, _POS
            elif total < 0:
                tb, tf = _TOTAL_NEG_BG, _NEG
            else:
                tb, tf = "#45475a", _ZERO
            self._total_val.config(text=total_text, bg=tb, fg=tf)
            self._total_frame.pack(fill=tk.X, pady=(0, 6))

            self._clear_frame(self._parts_frame)
            if no_formula:
                tk.Label(
                    self._parts_frame,
                    text="Kéo reward vào « Công thức tổng » để bắt đầu tính điểm",
                    bg=_REWARD_BG,
                    fg=_HINT_FG,
                    font=("", 8, "italic"),
                    anchor=tk.W,
                    wraplength=360,
                    justify=tk.LEFT,
                ).pack(fill=tk.X, pady=(0, 4))
            elif parts:
                tk.Label(
                    self._parts_frame,
                    text="Chi tiết cộng / trừ:",
                    bg=_REWARD_BG,
                    fg="#a6adc8",
                    font=("", 8, "bold"),
                    anchor=tk.W,
                ).pack(fill=tk.X, pady=(0, 4))
            for i, (label, chip_bg, chip_fg, val) in enumerate(parts):
                row_bg = "#3b3d52" if i % 2 else _REWARD_BG
                row = tk.Frame(self._parts_frame, bg=row_bg)
                row.pack(fill=tk.X, pady=1, padx=0)
                tk.Label(
                    row,
                    text=" %s " % label,
                    bg=chip_bg,
                    fg=chip_fg,
                    font=("", 8, "bold"),
                    padx=4,
                    pady=2,
                ).pack(side=tk.LEFT, padx=(0, 4))
                if val > 0:
                    vfg, vsign = _POS, "+"
                elif val < 0:
                    vfg, vsign = _NEG, ""
                else:
                    vfg, vsign = _ZERO, ""
                tk.Label(
                    row,
                    text="%s%.1f" % (vsign, val),
                    bg=row_bg,
                    fg=vfg,
                    font=("Consolas", 11, "bold"),
                    anchor=tk.E,
                ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 4))
            self._parts_frame.pack(fill=tk.X)
        else:
            self._action_lbl.pack_forget()
            self._total_frame.pack_forget()
            self._parts_frame.pack_forget()
            if hasattr(self, "_hint_lbl"):
                self._hint_lbl.pack(fill=tk.X, pady=4)

    def set_result_text(self, text):
        """Tương thích cũ — parse tối thiểu."""
        self.set_result_display(state_rows=text.splitlines(), has_action=False)

    def _reset(self):
        self.world.reset_scenario()
        self.redraw()
        self._notify()

    def _action(self, name):
        if self.on_change:
            self.on_change(name)

    def _notify(self):
        if self.on_change:
            self.on_change(None)

    def _size(self):
        w = self.world.sim_map["width"]
        h = self.world.sim_map["height"]
        return w, h, w * CELL + 2 * MARGIN, h * CELL + 2 * MARGIN

    def _cell_px(self, x, y):
        _, h, _, _ = self._size()
        return MARGIN + x * CELL, MARGIN + (h - 1 - y) * CELL

    def _cell_center(self, x, y):
        px, py = self._cell_px(x, y)
        return px + CELL // 2, py + CELL // 2

    def _pick_cell(self, px, py):
        _, h, _, _ = self._size()
        x = int((px - MARGIN) // CELL)
        y = h - 1 - int((py - MARGIN) // CELL)
        w = self.world.sim_map["width"]
        if is_valid(x, y, w, h):
            return x, y
        return None

    def _pick_edge(self, px, py):
        w, h, _, _ = self._size()
        best = None
        best_d = 999
        for y in range(h):
            for x in range(w):
                for d, x1, y1, x2, y2 in self._edge_lines(x, y):
                    dseg = self._point_seg_dist(px, py, x1, y1, x2, y2)
                    if dseg < best_d and dseg < max(8, CELL // 3):
                        best_d = dseg
                        best = (x, y, d)
        return best

    def _edge_lines(self, x, y):
        px, py = self._cell_px(x, y)
        return [
            ("N", px, py, px + CELL, py),
            ("E", px + CELL, py, px + CELL, py + CELL),
            ("S", px, py + CELL, px + CELL, py + CELL),
            ("W", px, py, px, py + CELL),
        ]

    @staticmethod
    def _point_seg_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        qx, qy = x1 + t * dx, y1 + t * dy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

    def _on_click(self, event):
        c = self.canvas
        px, py = c.canvasx(event.x), c.canvasy(event.y)
        tool = self._tool.get()
        if tool == "wall":
            edge = self._pick_edge(px, py)
            if edge:
                self.world.toggle_wall(*edge)
        else:
            cell = self._pick_cell(px, py)
            if not cell:
                return
            x, y = cell
            if tool == "robot":
                self.world.place_robot(x, y)
            elif tool == "goal":
                self.world.place_goal(x, y)
            elif tool == "cp":
                self.world.place_checkpoint(x, y)
        self.redraw()
        self._notify()

    def redraw(self):
        c = self.canvas
        c.addtag_all("old")
        sim = self.world.sim_map
        w, h, cw, ch = self._size()
        vis_w = min(cw, _MAX_CANVAS_W)
        c.config(width=vis_w, height=ch, scrollregion=(0, 0, cw, ch))
        goal = tuple(sim.get("goal") or (w - 1, h - 1))
        cps = [tuple(p) for p in (sim.get("checkpoints") or [])]
        walls = self.world.walls_set()
        rx, ry = self.world.robot["x"], self.world.robot["y"]
        rd = self.world.robot["direct"]

        for y in range(h):
            for x in range(w):
                px, py = self._cell_px(x, y)
                fill = "#313244"
                if (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cps:
                    fill = "#f9e2af"
                c.create_rectangle(px, py, px + CELL, py + CELL, fill=fill, outline="#45475a")

        for y in range(h):
            for x in range(w):
                px, py = self._cell_px(x, y)
                for d, x1, y1, x2, y2 in self._edge_lines(x, y):
                    nx, ny = neighbor_xy(x, y, d)
                    if not is_valid(nx, ny, w, h):
                        c.create_line(x1, y1, x2, y2, fill="#11111b", width=3)
                        continue
                    key = (x, y, d)
                    if key in walls:
                        c.create_line(x1, y1, x2, y2, fill="#f38ba8", width=4)

        rcx, rcy = self._cell_center(rx, ry)
        r = max(4, CELL // 5)
        c.create_oval(rcx - r, rcy - r, rcx + r, rcy + r, fill="#cba6f7", outline="#cdd6f4", width=2)
        arrow_len = max(8, CELL // 3)
        dir_arrow = {"N": (0, -arrow_len), "E": (arrow_len, 0), "S": (0, arrow_len), "W": (-arrow_len, 0)}
        dx, dy = dir_arrow.get(rd, (0, -arrow_len))
        c.create_line(rcx, rcy, rcx + dx, rcy + dy, fill="#1e1e2e", width=2, arrow=tk.LAST)
        c.delete("old")
