"""Map 12×5 tương tác — đặt robot, goal, CP, tường."""

import tkinter as tk
from tkinter import ttk

from RL_lib.grid import neighbor_xy, is_valid
from Ui_app.ui_scale import checkpoint_label_font, checkpoint_label_inset, font, px as scale_px
from Ui_app.ui_chips import make_result_chip
from Ui_app.map_layout import apply_fixed_canvas, avail_width_from_wrap, fit_grid_layout_tight

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
        self.frame = ttk.LabelFrame(parent, text="Check State", padding=scale_px(4))
        self.frame.pack(fill=tk.BOTH, expand=True, anchor=tk.N)

        self._selection = None
        self._await_new_cp = False
        self._resize_after_id = None
        self._last_avail_w = None
        self._cell = scale_px(35)
        self._offset_x = 0
        self._offset_y = 0

        tools = ttk.Frame(self.frame)
        tools.pack(fill=tk.X, pady=(0, 4))
        self.btn_add_cp = ttk.Button(tools, text="Thêm checkpoint", command=self.add_checkpoint)
        self.btn_add_cp.pack(side=tk.LEFT, padx=scale_px(2))
        self.btn_remove_cp = ttk.Button(tools, text="Xóa checkpoint", command=self.remove_selected_checkpoint)
        self.btn_remove_cp.pack(side=tk.LEFT, padx=scale_px(2))
        ttk.Button(tools, text="Reset State", command=self._reset_state).pack(
            side=tk.RIGHT, padx=scale_px(2)
        )
        ttk.Button(tools, text="Reset map", command=self._reset).pack(side=tk.RIGHT, padx=scale_px(2))

        self._map_wrap = ttk.Frame(self.frame)
        self._map_wrap.pack(fill=tk.X)
        self.canvas = tk.Canvas(
            self._map_wrap,
            bg="#1e1e2e",
            highlightthickness=0,
            cursor="crosshair",
            takefocus=1,
        )
        self.canvas.pack(anchor=tk.NW)
        self.canvas.bind("<Button-1>", self._on_click)
        self._map_wrap.bind("<Configure>", self._on_map_wrap_resize)
        self.frame.bind("<Configure>", self._on_map_wrap_resize, add="+")

        act_row = ttk.Frame(self.frame)
        self._act_row = act_row
        act_row.pack(fill=tk.X, pady=(scale_px(2), scale_px(2)))
        ttk.Label(act_row, text="Move:", font=font(9)).pack(side=tk.LEFT, padx=(0, scale_px(4)))
        self._move_btns = []
        for label, cmd in (
            ("(A/←) Rotate Left", lambda: self._action("rotate left")),
            ("(S/↑) Forward", lambda: self._action("forward")),
            ("(D/→) Rotate Right", lambda: self._action("rotate right")),
        ):
            btn = ttk.Button(act_row, text=label, command=cmd)
            btn.pack(side=tk.LEFT, padx=scale_px(2))
            self._move_btns.append(btn)
        self._move_enabled = True
        self._state_labels = []
        self._parts_sig = None
        self._part_rows = []
        self._key_actions = {
            "s": "forward",
            "a": "rotate left",
            "d": "rotate right",
            "up": "forward",
            "left": "rotate left",
            "right": "rotate right",
        }

        self._build_result_panel()
        self.set_result_display(state_rows=[], has_action=False)

        self._bind_keyboard()
        self.redraw()
        self._update_tool_buttons()

    def _on_map_wrap_resize(self, event=None):
        aw = self._avail_width()
        if aw < scale_px(40):
            return
        if aw == self._last_avail_w and self._resize_after_id is None:
            return
        self._last_avail_w = aw
        if self._resize_after_id:
            self._map_wrap.after_cancel(self._resize_after_id)
        self._resize_after_id = self._map_wrap.after(80, self._redraw_after_resize)

    def _avail_width(self) -> int:
        self.frame.update_idletasks()
        self._map_wrap.update_idletasks()
        aw = avail_width_from_wrap(self._map_wrap, min_w=180)
        if aw < scale_px(180):
            aw = max(scale_px(180), self.frame.winfo_width() - scale_px(12))
        return aw

    def _redraw_after_resize(self):
        self._resize_after_id = None
        self.redraw()

    def _layout_metrics(self):
        w = self.world.sim_map["width"]
        h = self.world.sim_map["height"]
        aw = self._avail_width()
        # Tight: cell theo chiều ngang; không đọc height wrap (bám canvas cũ khi co/giãn)
        cell, ox, oy, cw, ch = fit_grid_layout_tight(
            w, h, aw, max_cell=scale_px(60)
        )
        self._cell = cell
        self._offset_x = ox
        self._offset_y = oy
        self._last_avail_w = aw
        return cell, w, h, cw, ch

    def _apply_canvas_geometry(self, cw, ch):
        apply_fixed_canvas(self.canvas, cw, ch)

    def _bind_keyboard(self):
        self.canvas.bind("<Escape>", self._on_escape)
        self.canvas.bind("<Delete>", self._on_delete_key)
        self.canvas.bind("<BackSpace>", self._on_delete_key)

    def handle_key_event(self, event):
        if not self._move_enabled:
            return
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry)):
            return
        try:
            wclass = w.winfo_class()
        except tk.TclError:
            wclass = ""
        if wclass in ("TSpinbox", "Spinbox"):
            return
        action = self._key_actions.get(event.keysym.lower())
        if not action:
            return
        self._action(action)
        return "break"

    def _build_result_panel(self):
        outer = ttk.Frame(self.frame)
        self._result_outer = outer
        outer.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self._state_box = tk.LabelFrame(
            outer, text=" STATE ", font=font(10, weight="bold"), bg=_STATE_BG, fg=_STATE_FG, padx=scale_px(8), pady=scale_px(6)
        )
        self._state_box.pack(fill=tk.X, pady=(0, 4))
        self._state_inner = tk.Frame(self._state_box, bg=_STATE_BG)
        self._state_inner.pack(fill=tk.X)

        self._reward_box = tk.LabelFrame(
            outer, text=" REWARD ", font=font(10, weight="bold"), bg=_REWARD_BG, fg=_REWARD_FG, padx=scale_px(8), pady=scale_px(6)
        )
        self._reward_box.pack(fill=tk.BOTH, expand=True)
        reward_wrap = tk.Frame(self._reward_box, bg=_REWARD_BG)
        reward_wrap.pack(fill=tk.BOTH, expand=True)
        self._reward_canvas = tk.Canvas(
            reward_wrap,
            bg=_REWARD_BG,
            highlightthickness=0,
            bd=0,
            height=scale_px(570)
        )
        self._reward_scroll = ttk.Scrollbar(reward_wrap, orient=tk.VERTICAL, command=self._reward_canvas.yview)
        self._reward_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._reward_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._reward_inner = tk.Frame(self._reward_canvas, bg=_REWARD_BG)
        self._reward_canvas_win = self._reward_canvas.create_window((0, 0), window=self._reward_inner, anchor=tk.NW)
        self._reward_canvas.configure(yscrollcommand=self._reward_scroll.set)

        def _on_reward_inner_configure(_event=None):
            try:
                self._reward_canvas.configure(scrollregion=self._reward_canvas.bbox("all"))
            except tk.TclError:
                pass

        def _on_reward_canvas_configure(event):
            try:
                self._reward_canvas.itemconfigure(self._reward_canvas_win, width=event.width)
            except tk.TclError:
                pass

        self._reward_inner.bind("<Configure>", _on_reward_inner_configure)
        self._reward_canvas.bind("<Configure>", _on_reward_canvas_configure)
        self._bind_reward_wheel_tree(self._reward_canvas)

        self._action_lbl = tk.Label(
            self._reward_inner, text="", bg=_REWARD_BG, fg="#89b4fa", font=font(10, weight="bold"), anchor=tk.W
        )
        self._action_lbl.pack(fill=tk.X, pady=(0, 4))

        self._total_frame = tk.Frame(self._reward_inner, bg=_REWARD_BG)
        self._total_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            self._total_frame, text="TỔNG", bg=_REWARD_BG, fg=_REWARD_FG, font=font(11, weight="bold")
        ).pack(side=tk.LEFT, padx=(0, scale_px(8)))
        self._total_val = tk.Label(
            self._total_frame, text="", font=font(15, weight="bold"), padx=scale_px(10), pady=scale_px(4)
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
        return formula.replace(" + ", "\n  + ").replace(" - ", "\n  − ").replace(" * ", "\n  × ").replace(" / ", "\n  ÷ ").replace(" ^ ", "\n  ^ ")

    def _clear_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _bind_reward_wheel_tree(self, widget):
        if not getattr(widget, "_reward_wheel_tag", False):
            widget._reward_wheel_tag = True

            def _on_wheel(event):
                c = self._reward_canvas
                if event.delta:
                    c.yview_scroll(int(-event.delta / 120), "units")
                elif event.num == 4:
                    c.yview_scroll(-1, "units")
                elif event.num == 5:
                    c.yview_scroll(1, "units")
                return "break"

            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                widget.bind(seq, _on_wheel, add="+")
        for child in widget.winfo_children():
            self._bind_reward_wheel_tree(child)

    def _update_state_rows(self, state_rows):
        while len(self._state_labels) < len(state_rows):
            lbl = tk.Label(
                self._state_inner,
                text="",
                bg=_STATE_BG,
                fg=_STATE_FG,
                font=font(11, family="Consolas"),
                anchor=tk.W,
            )
            lbl.pack(fill=tk.X, pady=1)
            self._state_labels.append(lbl)
        while len(self._state_labels) > len(state_rows):
            lbl = self._state_labels.pop()
            lbl.destroy()
        for lbl, text in zip(self._state_labels, state_rows):
            if lbl.cget("text") != text:
                lbl.config(text=text)

    def _clear_parts_rows(self):
        for row in self._part_rows:
            try:
                row["frame"].destroy()
            except tk.TclError:
                pass
        self._part_rows = []
        self._parts_sig = None

    def _update_parts_rows(self, parts):
        sig = tuple(p[0] for p in parts)
        if sig == self._parts_sig and len(self._part_rows) == len(parts):
            for (_, _, _, val), row in zip(parts, self._part_rows):
                if val > 0:
                    vfg, vsign = _POS, "+"
                elif val < 0:
                    vfg, vsign = _NEG, ""
                else:
                    vfg, vsign = _ZERO, ""
                text = "%s%.1f" % (vsign, val)
                if row["val_lbl"].cget("text") != text or row["val_lbl"].cget("fg") != vfg:
                    row["val_lbl"].config(text=text, fg=vfg)
            return

        self._clear_frame(self._parts_frame)
        self._part_rows = []
        self._parts_sig = sig
        if parts:
            tk.Label(
                self._parts_frame,
                text="Chi tiết thành phần:",
                bg=_REWARD_BG,
                fg="#a6adc8",
                font=font(9, weight="bold"),
                anchor=tk.W,
            ).pack(fill=tk.X, pady=(0, 4))
        for i, (label, chip_bg, chip_fg, val) in enumerate(parts):
            row_bg = "#3b3d52" if i % 2 else _REWARD_BG
            row = tk.Frame(self._parts_frame, bg=row_bg)
            row.pack(fill=tk.X, pady=1, padx=0)
            make_result_chip(row, label, chip_bg, chip_fg, row_bg, font(9, weight="bold"))
            if val > 0:
                vfg, vsign = _POS, "+"
            elif val < 0:
                vfg, vsign = _NEG, ""
            else:
                vfg, vsign = _ZERO, ""
            val_lbl = tk.Label(
                row,
                text="%s%.1f" % (vsign, val),
                bg=row_bg,
                fg=vfg,
                font=font(12, weight="bold", family="Consolas"),
                anchor=tk.E,
            )
            val_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 4))
            self._part_rows.append({"frame": row, "val_lbl": val_lbl})

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
        parts = parts or []
        self._update_state_rows(state_rows)

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

            if no_formula:
                self._clear_parts_rows()
                self._clear_frame(self._parts_frame)
                tk.Label(
                    self._parts_frame,
                    text="Kéo reward vào « Công thức tổng » để bắt đầu tính điểm",
                    bg=_REWARD_BG,
                    fg=_HINT_FG,
                    font=font(9, weight="italic"),
                    anchor=tk.W,
                    wraplength=scale_px(360),
                    justify=tk.LEFT,
                ).pack(fill=tk.X, pady=(0, 4))
            elif parts:
                self._update_parts_rows(parts)
            else:
                self._clear_parts_rows()
                self._clear_frame(self._parts_frame)
            self._parts_frame.pack(fill=tk.X)
        else:
            self._action_lbl.pack_forget()
            self._total_frame.pack_forget()
            self._parts_frame.pack_forget()
            self._clear_parts_rows()
            if hasattr(self, "_hint_lbl"):
                self._hint_lbl.pack(fill=tk.X, pady=4)
        self._bind_reward_wheel_tree(self._reward_inner)

    def set_result_text(self, text):
        """Tương thích cũ — parse tối thiểu."""
        self.set_result_display(state_rows=text.splitlines(), has_action=False)

    def set_move_enabled(self, enabled):
        self._move_enabled = bool(enabled)
        state = tk.NORMAL if self._move_enabled else tk.DISABLED
        for btn in self._move_btns:
            try:
                btn.configure(state=state)
            except tk.TclError:
                pass

    def _reset(self):
        self.world.reset_scenario()
        self.redraw()
        self._notify()

    def _reset_state(self):
        self.world.reset_runtime_state()
        self.redraw()
        self._notify()

    def _action(self, name):
        if not self._move_enabled:
            return
        if self.on_change:
            self.on_change(name)

    def _notify(self):
        if self.on_change:
            self.on_change(None)

    def _size(self):
        w = self.world.sim_map["width"]
        h = self.world.sim_map["height"]
        cell = self._cell
        cw = max(self._offset_x * 2 + w * cell, w * cell)
        ch = max(self._offset_y * 2 + h * cell, h * cell)
        return w, h, cw, ch

    def _cell_px(self, x, y):
        h = self.world.sim_map["height"]
        return self._offset_x + x * self._cell, self._offset_y + (h - 1 - y) * self._cell

    def _cell_center(self, x, y):
        px0, py0 = self._cell_px(x, y)
        return px0 + self._cell // 2, py0 + self._cell // 2

    def _pick_cell(self, px, py):
        cell = self._cell
        h = self.world.sim_map["height"]
        x = int((px - self._offset_x) // cell)
        y = h - 1 - int((py - self._offset_y) // cell)
        w = self.world.sim_map["width"]
        if is_valid(x, y, w, h):
            return x, y
        return None

    def _pick_edge(self, px, py):
        cell = self._cell
        w, h, _, _ = self._size()
        best = None
        best_d = 999
        for y in range(h):
            for x in range(w):
                for d, x1, y1, x2, y2 in self._edge_lines(x, y):
                    dseg = self._point_seg_dist(px, py, x1, y1, x2, y2)
                    if dseg < best_d and dseg < max(scale_px(8), cell // 3):
                        best_d = dseg
                        best = (x, y, d)
        return best

    def _edge_lines(self, x, y):
        cell = self._cell
        px0, py0 = self._cell_px(x, y)
        return [
            ("N", px0, py0, px0 + cell, py0),
            ("E", px0 + cell, py0, px0 + cell, py0 + cell),
            ("S", px0, py0 + cell, px0 + cell, py0 + cell),
            ("W", px0, py0, px0, py0 + cell),
        ]

    @staticmethod
    def _point_seg_dist(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        qx, qy = x1 + t * dx, y1 + t * dy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

    def add_checkpoint(self):
        cps = self.world.sim_map.get("checkpoints") or []
        if len(cps) >= 3:
            return
        self._await_new_cp = True
        self._selection = None
        self._update_tool_buttons()
        self.redraw()

    def remove_selected_checkpoint(self):
        if not self._selection or self._selection[0] != "cp":
            return
        idx = self._selection[1]
        sim = self.world.sim_map
        cps = list(sim.get("checkpoints") or [])
        if 0 <= idx < len(cps):
            cps.pop(idx)
            sim["checkpoints"] = cps
            self.world.rmap["checkpoints"] = cps
            self.world.sync_maps()
            self._clear_selection()
            self.redraw()
            self._notify()

    def _clear_selection(self):
        self._selection = None
        self._await_new_cp = False
        self._update_tool_buttons()

    def _update_tool_buttons(self):
        if not hasattr(self, "btn_add_cp"):
            return
        cps = self.world.sim_map.get("checkpoints") or []
        self.btn_add_cp.configure(state=tk.NORMAL if len(cps) < 3 else tk.DISABLED)
        cp_selected = self._selection and self._selection[0] == "cp"
        self.btn_remove_cp.configure(state=tk.NORMAL if cp_selected and cps else tk.DISABLED)

    def _on_escape(self, _event=None):
        self._clear_selection()
        self.redraw()

    def _on_delete_key(self, _event=None):
        if self._selection and self._selection[0] == "cp":
            self.remove_selected_checkpoint()

    def _special_at(self, x, y):
        sim = self.world.sim_map
        if (x, y) == (self.world.robot["x"], self.world.robot["y"]):
            return "robot"
        if (x, y) == tuple(sim.get("goal") or (0, 0)):
            return "goal"
        cps = [tuple(p) for p in (sim.get("checkpoints") or [])]
        cp_index = {cp: i for i, cp in enumerate(cps)}
        for i, cp in enumerate(cps):
            if (x, y) == cp:
                return ("cp", i)
        return None

    def _occupied(self, x, y, ignore=None):
        sim = self.world.sim_map
        if ignore != "robot" and (x, y) == (self.world.robot["x"], self.world.robot["y"]):
            return True
        if ignore != "goal" and (x, y) == tuple(sim.get("goal") or (0, 0)):
            return True
        cps = [tuple(p) for p in (sim.get("checkpoints") or [])]
        for i, cp in enumerate(cps):
            if ignore == ("cp", i):
                continue
            if (x, y) == cp:
                return True
        return False

    def _selection_cell(self):
        if not self._selection:
            return None
        kind = self._selection[0]
        if kind == "robot":
            return (self.world.robot["x"], self.world.robot["y"])
        if kind == "goal":
            return tuple(self.world.sim_map.get("goal") or (0, 0))
        if kind == "cp":
            i = self._selection[1]
            cps = [tuple(p) for p in (self.world.sim_map.get("checkpoints") or [])]
            if 0 <= i < len(cps):
                return cps[i]
        return None

    def _handle_cell_click(self, cell):
        x, y = cell
        sim = self.world.sim_map

        if self._await_new_cp:
            if self._occupied(x, y):
                return
            cps = list(sim.get("checkpoints") or [])
            cps.append((x, y))
            sim["checkpoints"] = cps
            self.world.rmap["checkpoints"] = cps
            self.world.sync_maps()
            self._await_new_cp = False
            self._selection = ("cp", len(cps) - 1)
            self._update_tool_buttons()
            self.redraw()
            self._notify()
            return

        if self._selection:
            if cell == self._selection_cell():
                self._clear_selection()
                self.redraw()
                return
            if self._occupied(x, y, ignore=self._selection):
                return
            kind = self._selection[0]
            if kind == "robot":
                self.world.place_robot(x, y)
            elif kind == "goal":
                self.world.place_goal(x, y)
            elif kind == "cp":
                idx = self._selection[1]
                cps = list(sim.get("checkpoints") or [])
                if 0 <= idx < len(cps):
                    cps[idx] = (x, y)
                    sim["checkpoints"] = cps
                    self.world.rmap["checkpoints"] = cps
                    self.world.sync_maps()
            self._clear_selection()
            self.redraw()
            self._notify()
            return

        special = self._special_at(x, y)
        if special == "robot":
            self._selection = ("robot",)
        elif special == "goal":
            self._selection = ("goal",)
        elif isinstance(special, tuple) and special[0] == "cp":
            self._selection = special
        self._update_tool_buttons()
        self.redraw()

    def _on_click(self, event):
        c = self.canvas
        px, py = c.canvasx(event.x), c.canvasy(event.y)
        edge = self._pick_edge(px, py)
        if edge:
            w, h, _, _ = self._size()
            nx, ny = neighbor_xy(edge[0], edge[1], edge[2])
            if is_valid(nx, ny, w, h):
                self.world.toggle_wall(*edge)
                self._clear_selection()
                self.redraw()
                self._notify()
                return

        cell = self._pick_cell(px, py)
        if cell is None:
            return
        self._handle_cell_click(cell)
        self._notify()

    def _draw_edge_wall(self, d, px, py, cell, thick, blocked=False):
        c = self.canvas
        half = max(2, thick // 2)
        inset = max(2, cell // 18)
        x0, x1 = px + inset, px + cell - inset
        y0, y1 = py + inset, py + cell - inset
        if d == "N":
            coords = (x0, py - half, x1, py + half)
        elif d == "S":
            coords = (x0, py + cell - half, x1, py + cell + half)
        elif d == "W":
            coords = (px - half, y0, px + half, y1)
        else:  # E
            coords = (px + cell - half, y0, px + cell + half, y1)
        if blocked:
            c.create_rectangle(*coords, fill="#e64566", outline="#ffccd5", width=1)
        else:
            c.create_rectangle(*coords, fill="#0a0a0f", outline="#313244", width=1)

    def redraw(self):
        c = self.canvas
        c.addtag_all("old")
        sim = self.world.sim_map
        cell, w, h, cw, ch = self._layout_metrics()
        self._apply_canvas_geometry(cw, ch)
        start = tuple(sim.get("start") or (0, 0))
        goal = tuple(sim.get("goal") or (w - 1, h - 1))
        cps = [tuple(p) for p in (sim.get("checkpoints") or [])]
        cp_index = {cp: i for i, cp in enumerate(cps)}
        walls = self.world.walls_set()
        rx, ry = self.world.robot["x"], self.world.robot["y"]
        rd = self.world.robot["direct"]

        blocked_thick = max(scale_px(6), min(scale_px(10), cell // 9))
        open_w = max(2, min(3, cell // 18))
        border_thick = max(scale_px(6), min(scale_px(9), cell // 10))

        # Draw grid cells
        for y in range(h):
            for x in range(w):
                px0, py0 = self._cell_px(x, y)
                fill = "#313244"
                if (x, y) == start:
                    fill = "#a6e3a1"
                elif (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cp_index:
                    try:
                        idx = cp_index[(x, y)]
                        visited = self.world.robot.get("cp_visited") or []
                        if idx < len(visited) and visited[idx]:
                            fill = "#89dceb"
                        else:
                            fill = "#f9e2af"
                    except ValueError:
                        fill = "#f9e2af"
                c.create_rectangle(px0, py0, px0 + cell, py0 + cell, fill=fill, outline="#45475a")
                if (x, y) in cp_index:
                    inset = checkpoint_label_inset(cell)
                    c.create_text(
                        px0 + cell - inset,
                        py0 + inset,
                        text="%d" % (cp_index[(x, y)] + 1),
                        fill="#11111b",
                        font=checkpoint_label_font(cell),
                        anchor=tk.NE,
                    )

        sel_cell = self._selection_cell()
        if sel_cell:
            sx, sy = sel_cell
            px0, py0 = self._cell_px(sx, sy)
            pad = max(3, cell // 14)
            c.create_rectangle(
                px0 + pad,
                py0 + pad,
                px0 + cell - pad,
                py0 + cell - pad,
                outline="#89b4fa",
                width=3,
                dash=(6, 4),
            )

        if self._await_new_cp:
            c.create_text(
                cw // 2,
                scale_px(12),
                text="Bấm ô để đặt checkpoint mới (Esc: hủy)",
                fill="#89b4fa",
                font=font(9, weight="bold"),
            )

        # Draw walls
        for y in range(h):
            for x in range(w):
                px0, py0 = self._cell_px(x, y)
                for d, x1, y1, x2, y2 in self._edge_lines(x, y):
                    nx, ny = neighbor_xy(x, y, d)
                    if not is_valid(nx, ny, w, h):
                        self._draw_edge_wall(d, px0, py0, cell, border_thick, blocked=False)
                        continue
                    key = (x, y, d)
                    if key in walls:
                        self._draw_edge_wall(d, px0, py0, cell, blocked_thick, blocked=True)
                    else:
                        c.create_line(x1, y1, x2, y2, fill="#56586e", width=open_w)

        rcx, rcy = self._cell_center(rx, ry)
        r = max(4, cell // 5)
        c.create_oval(rcx - r, rcy - r, rcx + r, rcy + r, fill="#cba6f7", outline="#cdd6f4", width=2)
        arrow_len = max(scale_px(8), cell // 3)
        dir_arrow = {"N": (0, -arrow_len), "E": (arrow_len, 0), "S": (0, arrow_len), "W": (-arrow_len, 0)}
        dx, dy = dir_arrow.get(rd, (0, -arrow_len))
        c.create_line(rcx, rcy, rcx + dx, rcy + dy, fill="#1e1e2e", width=2, arrow=tk.LAST)
        c.delete("old")
