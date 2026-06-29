"""
UI tạo / chỉnh map — grid, bấm cạnh để chặn / mở, lưu JSON train hoặc infer.
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SIM = os.path.join(_ROOT, "Simulation")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from map.map_io import (
    TRAIN_MAPS_DIR,
    INFER_MAPS_DIR,
    default_spec,
    load_map_json,
    save_map_json,
    walls_set_from_spec,
    spec_from_walls,
    list_map_files,
)
from RL_lib.grid import DIRECTIONS, neighbor_xy, is_valid

CELL_MIN = 36
CELL_MAX = 80
CANVAS_PAD = 28
EDGE_HIT = 10


class MapEditorApp:
    def __init__(self, parent=None, root=None, on_saved=None):
        if parent is None:
            self.root = tk.Tk()
            self.root.title("SS26 Map Editor")
            self.root.minsize(720, 560)
            self.container = self.root
            self._standalone = True
        else:
            self.root = root or parent.winfo_toplevel()
            self.container = parent
            self._standalone = False

        self._on_saved = on_saved

        self.width = 10
        self.height = 10
        self.walls = set()
        self.map_name = tk.StringVar(value="custom_01")
        self.kind = tk.StringVar(value="train")
        self.start_x = tk.IntVar(value=0)
        self.start_y = tk.IntVar(value=0)
        self.goal_x = tk.IntVar(value=9)
        self.goal_y = tk.IntVar(value=9)
        self.checkpoints = []
        self._selection = None  # ('start',) | ('goal',) | ('cp', index)
        self._await_new_cp = False
        self._pos_label = tk.StringVar(value="")
        self._cell = 52
        self._offset_x = CANVAS_PAD
        self._offset_y = CANVAS_PAD
        self._edge_hit = EDGE_HIT

        self._build_toolbar()
        self._build_canvas()
        self._build_status()
        self.apply_size()
        self.root.after_idle(self.redraw)

    def _build_toolbar(self):
        bar = ttk.Frame(self.container, padding=8)
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="Width").grid(row=0, column=0, padx=(0, 4))
        self.spin_w = ttk.Spinbox(bar, from_=3, to=40, width=4, command=self._noop)
        self.spin_w.set(str(self.width))
        self.spin_w.grid(row=0, column=1, padx=(0, 12))

        ttk.Label(bar, text="Height").grid(row=0, column=2, padx=(0, 4))
        self.spin_h = ttk.Spinbox(bar, from_=3, to=40, width=4)
        self.spin_h.set(str(self.height))
        self.spin_h.grid(row=0, column=3, padx=(0, 12))

        ttk.Button(bar, text="Apply size", command=self.apply_size).grid(row=0, column=4, padx=4)

        ttk.Separator(bar, orient=tk.VERTICAL).grid(row=0, column=5, sticky="ns", padx=12)

        ttk.Label(bar, text="Name").grid(row=0, column=6, padx=(0, 4))
        ttk.Entry(bar, textvariable=self.map_name, width=14).grid(row=0, column=7, padx=(0, 12))

        ttk.Label(bar, text="Save as").grid(row=0, column=8, padx=(0, 4))
        ttk.Radiobutton(bar, text="train", variable=self.kind, value="train").grid(row=0, column=9)
        ttk.Radiobutton(bar, text="infer", variable=self.kind, value="infer").grid(row=0, column=10, padx=(0, 12))

        row2 = ttk.Frame(self.container, padding=(8, 0, 8, 8))
        row2.pack(fill=tk.X)

        ttk.Label(row2, textvariable=self._pos_label).pack(side=tk.LEFT, padx=(0, 12))

        self.btn_add_cp = ttk.Button(row2, text="Thêm checkpoint", command=self.add_checkpoint)
        self.btn_add_cp.pack(side=tk.LEFT, padx=(0, 4))
        self.btn_remove_cp = ttk.Button(row2, text="Xóa checkpoint", command=self.remove_selected_checkpoint)
        self.btn_remove_cp.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(row2, text="Load JSON…", command=self.load_json).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Save JSON", command=self.save_json).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Clear walls", command=self.clear_walls).pack(side=tk.RIGHT, padx=4)

        self._update_pos_label()

    def _build_canvas(self):
        wrap = ttk.Frame(self.container, padding=8)
        wrap.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(wrap, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<Delete>", self._on_delete_key)
        self.root.bind("<BackSpace>", self._on_delete_key)

        # hint = ttk.Label(
        #     self.container,
        #     text=(
        #         "Cạnh giữa 2 ô: chặn / mở tường. "
        #         "Start / Goal / CP: bấm ô hiện tại → bấm ô đích để di chuyển. "
        #         "Thêm checkpoint: nút trên thanh công cụ rồi bấm ô (tối đa 3). "
        #         "Xóa: chọn CP rồi nút Xóa checkpoint hoặc phím Delete."
        #     ),
        #     padding=(8, 0),
        # )
        # hint.pack(fill=tk.X)

    def _build_status(self):
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.container, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W, padding=4).pack(
            fill=tk.X, side=tk.BOTTOM
        )

    def _on_escape(self, _event=None):
        if self._selection or self._await_new_cp:
            self._clear_selection()
            self.status.set("Đã hủy chọn.")
            self.redraw()

    def _on_delete_key(self, _event=None):
        if self._selection and self._selection[0] == "cp":
            self.remove_selected_checkpoint()

    def _noop(self):
        pass

    def cell_px(self, x, y):
        px = self._offset_x + x * self._cell
        py = self._offset_y + (self.height - 1 - y) * self._cell
        return px, py

    def _update_layout(self):
        """Scale ô map vừa canvas và căn giữa."""
        c = self.canvas
        c.update_idletasks()
        cw = max(c.winfo_width(), 320)
        ch = max(c.winfo_height(), 280)
        avail_w = max(cw - 2 * CANVAS_PAD, self.width * CELL_MIN)
        avail_h = max(ch - 2 * CANVAS_PAD, self.height * CELL_MIN)
        cell = int(min(avail_w / self.width, avail_h / self.height, CELL_MAX))
        self._cell = max(cell, CELL_MIN)
        map_w = self.width * self._cell
        map_h = self.height * self._cell
        self._offset_x = max(CANVAS_PAD, (cw - map_w) // 2)
        self._offset_y = max(CANVAS_PAD, (ch - map_h) // 2)
        self._edge_hit = max(8, min(18, self._cell // 4))
        c.config(scrollregion=(0, 0, cw, ch))
        return cw, ch

    def apply_size(self):
        try:
            w = int(self.spin_w.get())
            h = int(self.spin_h.get())
        except ValueError:
            messagebox.showerror("Size", "Width / height phải là số nguyên.")
            return
        if w < 3 or h < 3 or w > 40 or h > 40:
            messagebox.showerror("Size", "Kích thước map: 3–40.")
            return
        self.width = w
        self.height = h
        self.walls = {e for e in self.walls if self._edge_valid(*e)}
        self.goal_x.set(min(self.goal_x.get(), w - 1))
        self.goal_y.set(min(self.goal_y.get(), h - 1))
        self.start_x.set(min(self.start_x.get(), w - 1))
        self.start_y.set(min(self.start_y.get(), h - 1))
        self.checkpoints = [
            [min(cp[0], w - 1), min(cp[1], h - 1)] for cp in self.checkpoints if len(cp) >= 2
        ]
        self._clear_selection()
        self.redraw()
        self._update_pos_label()
        self.status.set("Map %d×%d" % (w, h))

    def _edge_valid(self, x, y, d):
        if not is_valid(x, y, self.width, self.height):
            return False
        nx, ny = neighbor_xy(x, y, d)
        return is_valid(nx, ny, self.width, self.height)

    def _start_pos(self):
        return (self.start_x.get(), self.start_y.get())

    def _goal_pos(self):
        return (self.goal_x.get(), self.goal_y.get())

    def _cp_positions(self):
        return [tuple(cp) for cp in self.checkpoints]

    def _special_at(self, x, y):
        if (x, y) == self._start_pos():
            return "start"
        if (x, y) == self._goal_pos():
            return "goal"
        for i, cp in enumerate(self.checkpoints):
            if len(cp) >= 2 and (x, y) == (cp[0], cp[1]):
                return ("cp", i)
        return None

    def _occupied(self, x, y, ignore=None):
        """ignore: 'start' | 'goal' | ('cp', i) — bỏ qua khi kiểm tra trùng."""
        if ignore != "start" and (x, y) == self._start_pos():
            return True
        if ignore != "goal" and (x, y) == self._goal_pos():
            return True
        for i, cp in enumerate(self.checkpoints):
            if ignore == ("cp", i):
                continue
            if len(cp) >= 2 and (x, y) == (cp[0], cp[1]):
                return True
        return False

    def _clear_selection(self):
        self._selection = None
        self._await_new_cp = False
        self._update_tool_buttons()

    def _update_tool_buttons(self):
        if not hasattr(self, "btn_add_cp"):
            return
        self.btn_add_cp.configure(state=tk.NORMAL if len(self.checkpoints) < 3 else tk.DISABLED)
        cp_selected = self._selection and self._selection[0] == "cp"
        self.btn_remove_cp.configure(
            state=tk.NORMAL if cp_selected and self.checkpoints else tk.DISABLED
        )

    def _update_pos_label(self):
        cp_txt = ""
        if self.checkpoints:
            cp_txt = " | CP: " + "; ".join("(%d,%d)" % (c[0], c[1]) for c in self.checkpoints)
        self._pos_label.set(
            "Start (%d,%d)  Goal (%d,%d)%s  (%d/3 CP)"
            % (
                self.start_x.get(),
                self.start_y.get(),
                self.goal_x.get(),
                self.goal_y.get(),
                cp_txt,
                len(self.checkpoints),
            )
        )
        self._update_tool_buttons()

    def _selection_cell(self):
        if not self._selection:
            return None
        kind = self._selection[0]
        if kind == "start":
            return self._start_pos()
        if kind == "goal":
            return self._goal_pos()
        if kind == "cp":
            i = self._selection[1]
            if 0 <= i < len(self.checkpoints):
                cp = self.checkpoints[i]
                return (cp[0], cp[1])
        return None

    def _set_selection(self, sel):
        self._selection = sel
        self._await_new_cp = False
        if sel == ("start",):
            self.status.set("✓ Đã chọn Start — bấm ô đích để di chuyển (Esc: bỏ chọn)")
        elif sel == ("goal",):
            self.status.set("✓ Đã chọn Goal — bấm ô đích để di chuyển (Esc: bỏ chọn)")
        elif sel and sel[0] == "cp":
            i = sel[1]
            cp = self.checkpoints[i]
            self.status.set(
                "✓ Đã chọn CP%d (%d,%d) — bấm ô đích để di chuyển; Delete / Xóa checkpoint để xóa"
                % (i + 1, cp[0], cp[1])
            )
        self._update_tool_buttons()
        self.redraw()

    def add_checkpoint(self):
        if len(self.checkpoints) >= 3:
            messagebox.showinfo("Checkpoint", "Tối đa 3 checkpoint.")
            return
        self._await_new_cp = True
        self._selection = None
        self.status.set("Đặt checkpoint mới — bấm một ô trên map (Esc: hủy)")
        self.redraw()

    def remove_selected_checkpoint(self):
        if not self._selection or self._selection[0] != "cp":
            self.status.set("Chọn một checkpoint trên map trước khi xóa.")
            return
        i = self._selection[1]
        if i < 0 or i >= len(self.checkpoints):
            self._clear_selection()
            return
        cp = self.checkpoints.pop(i)
        self._clear_selection()
        self._update_pos_label()
        self.redraw()
        self.status.set("Đã xóa CP tại (%d,%d) — còn %d checkpoint." % (cp[0], cp[1], len(self.checkpoints)))

    def _parse_checkpoints(self):
        return [list(cp) for cp in self.checkpoints]

    def _load_checkpoints(self, cps):
        self.checkpoints = [list(c) for c in (cps or [])][:3]

    def current_spec(self):
        return spec_from_walls(
            self.width,
            self.height,
            self.walls,
            name=self.map_name.get().strip() or "custom",
            kind=self.kind.get(),
            start=[self.start_x.get(), self.start_y.get()],
            goal=[self.goal_x.get(), self.goal_y.get()],
            checkpoints=self._parse_checkpoints(),
        )

    def load_spec(self, spec):
        self.width = int(spec["width"])
        self.height = int(spec["height"])
        self.spin_w.set(str(self.width))
        self.spin_h.set(str(self.height))
        self.map_name.set(spec.get("name", "custom"))
        self.kind.set(spec.get("kind", "train"))
        self.start_x.set(spec["start"][0])
        self.start_y.set(spec["start"][1])
        self.goal_x.set(spec["goal"][0])
        self.goal_y.set(spec["goal"][1])
        self._load_checkpoints(spec.get("checkpoints") or [])
        self.walls = walls_set_from_spec(spec)
        self._clear_selection()
        self._update_pos_label()
        self.redraw()
        self.status.set("Loaded: %s" % spec.get("name", "?"))

    def save_json(self):
        spec = self.current_spec()
        try:
            path = save_map_json(spec, kind=self.kind.get())
            path = os.path.abspath(path)
        except (OSError, ValueError, tk.TclError) as e:
            messagebox.showerror("Save", str(e))
            return
        self.status.set("Saved: %s" % path)
        folder = "train" if self.kind.get() == "train" else "infer"
        if self._on_saved:
            try:
                self._on_saved(self.kind.get(), path)
            except Exception:
                pass
        messagebox.showinfo("Saved", "Đã lưu vào map/%s/\n%s" % (folder, path))

    def load_json(self):
        kind = self.kind.get()
        initial = TRAIN_MAPS_DIR if kind == "train" else INFER_MAPS_DIR
        os.makedirs(initial, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Load map JSON",
            initialdir=initial,
            filetypes=[("Map JSON", "map_*.json"), ("JSON", "*.json")],
        )
        if not path:
            return
        try:
            spec = load_map_json(path)
            self.load_spec(spec)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            messagebox.showerror("Load", str(e))

    def clear_walls(self):
        self.walls.clear()
        self.redraw()
        self.status.set("Walls cleared")

    def on_click(self, event):
        edge = self.pick_edge(event.x, event.y)
        if edge is not None:
            if edge in self.walls:
                self.walls.remove(edge)
            else:
                self.walls.add(edge)
            self._clear_selection()
            self.redraw()
            x, y, d = edge
            blocked = edge in self.walls
            self.status.set("Edge (%d,%d) %s → %s" % (x, y, d, "blocked" if blocked else "open"))
            return

        cell = self.pick_cell(event.x, event.y)
        if cell is None:
            return
        self._handle_cell_click(cell)

    def _handle_cell_click(self, cell):
        x, y = cell

        if self._await_new_cp:
            if self._occupied(x, y):
                self.status.set("Ô (%d,%d) đã có Start/Goal/CP — chọn ô khác." % (x, y))
                return
            self.checkpoints.append([x, y])
            self._await_new_cp = False
            self._set_selection(("cp", len(self.checkpoints) - 1))
            self._update_pos_label()
            self.status.set("Đã thêm CP%d tại (%d,%d) — có thể bấm ô khác để di chuyển." % (len(self.checkpoints), x, y))
            return

        if self._selection:
            if cell == self._selection_cell():
                self._clear_selection()
                self.status.set("Đã bỏ chọn.")
                self.redraw()
                return
            if self._occupied(x, y, ignore=self._selection):
                self.status.set("Ô (%d,%d) trùng Start/Goal/CP khác — chọn ô trống." % (x, y))
                return
            kind = self._selection[0]
            if kind == "start":
                self.start_x.set(x)
                self.start_y.set(y)
                self.status.set("Start → (%d,%d)" % (x, y))
            elif kind == "goal":
                self.goal_x.set(x)
                self.goal_y.set(y)
                self.status.set("Goal → (%d,%d)" % (x, y))
            elif kind == "cp":
                self.checkpoints[self._selection[1]] = [x, y]
                self.status.set("CP%d → (%d,%d)" % (self._selection[1] + 1, x, y))
            self._clear_selection()
            self._update_pos_label()
            self.redraw()
            return

        special = self._special_at(x, y)
        if special == "start":
            self._set_selection(("start",))
        elif special == "goal":
            self._set_selection(("goal",))
        elif isinstance(special, tuple) and special[0] == "cp":
            self._set_selection(special)

    def pick_cell(self, cx, cy):
        for y in range(self.height):
            for x in range(self.width):
                px, py = self.cell_px(x, y)
                if px <= cx < px + self._cell and py <= cy < py + self._cell:
                    return (x, y)
        return None

    def pick_edge(self, cx, cy):
        best = None
        best_d = self._edge_hit + 1
        cell = self._cell
        for y in range(self.height):
            for x in range(self.width):
                px, py = self.cell_px(x, y)
                candidates = [
                    (x, y, "N", px, py, px + cell, py),
                    (x, y, "E", px + cell, py, px + cell, py + cell),
                    (x, y, "S", px, py + cell, px + cell, py + cell),
                    (x, y, "W", px, py, px, py + cell),
                ]
                for ex, ey, d, x1, y1, x2, y2 in candidates:
                    if not self._edge_valid(ex, ey, d):
                        continue
                    dist = self._point_seg_dist(cx, cy, x1, y1, x2, y2)
                    if dist < best_d:
                        best_d = dist
                        best = (ex, ey, d)
        return best if best_d <= self._edge_hit else None

    @staticmethod
    def _point_seg_dist(px, py, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        qx = x1 + t * dx
        qy = y1 + t * dy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5

    def _draw_edge_wall(self, c, d, px, py, cell, thick, blocked=False):
        """Vạch chặn nằm trên cạnh lưới (giữa 2 ô), không chiếm trong ô."""
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
        c.delete("all")
        cw, ch = self._update_layout()
        cell = self._cell
        font_sz = max(8, min(12, cell // 5))
        blocked_thick = max(6, min(10, cell // 9))
        open_w = max(2, min(3, cell // 18))
        border_thick = max(6, min(9, cell // 10))

        start = self._start_pos()
        goal = self._goal_pos()
        cps = {tuple(cp) for cp in self.checkpoints if len(cp) >= 2}
        sel_cell = self._selection_cell()

        for y in range(self.height):
            for x in range(self.width):
                px, py = self.cell_px(x, y)
                fill = "#313244"
                if (x, y) == start:
                    fill = "#a6e3a1"
                elif (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cps:
                    fill = "#f9e2af"
                c.create_rectangle(
                    px, py, px + cell, py + cell, fill=fill, outline="#45475a", width=1
                )
                label = "%d,%d" % (x, y)
                if sel_cell == (x, y):
                    label = "✓ " + label
                c.create_text(
                    px + cell // 2,
                    py + cell // 2,
                    text=label,
                    fill="#cdd6f4",
                    font=("", font_sz),
                )

        if sel_cell:
            sx, sy = sel_cell
            px, py = self.cell_px(sx, sy)
            pad = max(3, cell // 14)
            c.create_rectangle(
                px + pad,
                py + pad,
                px + cell - pad,
                py + cell - pad,
                outline="#89b4fa",
                width=3,
                dash=(6, 4),
            )

        if self._await_new_cp:
            c.create_text(
                cw // 2,
                max(16, self._offset_y // 2),
                text="← Bấm ô để đặt checkpoint mới",
                fill="#89b4fa",
                font=("", 10, "bold"),
            )

        for y in range(self.height):
            for x in range(self.width):
                px, py = self.cell_px(x, y)
                for d, x1, y1, x2, y2 in [
                    ("N", px, py, px + cell, py),
                    ("E", px + cell, py, px + cell, py + cell),
                    ("S", px, py + cell, px + cell, py + cell),
                    ("W", px, py, px, py + cell),
                ]:
                    if not self._edge_valid(x, y, d):
                        self._draw_edge_wall(c, d, px, py, cell, border_thick, blocked=False)
                        continue
                    key = (x, y, d)
                    if key in self.walls:
                        self._draw_edge_wall(c, d, px, py, cell, blocked_thick, blocked=True)
                    else:
                        c.create_line(x1, y1, x2, y2, fill="#56586e", width=open_w)

    def run(self):
        if self._standalone:
            self.root.mainloop()


def run_app(parent=None, root=None, on_saved=None):
    app = MapEditorApp(parent=parent, root=root, on_saved=on_saved)
    if parent is None:
        app.run()
    return app
