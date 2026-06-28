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

CELL = 44
MARGIN = 24
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
        self.cp_text = tk.StringVar(value="")

        self._build_toolbar()
        self._build_canvas()
        self._build_status()
        self.apply_size()

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

        ttk.Label(row2, text="Start (x,y)").pack(side=tk.LEFT)
        ttk.Spinbox(row2, from_=0, to=39, width=3, textvariable=self.start_x).pack(side=tk.LEFT, padx=2)
        ttk.Spinbox(row2, from_=0, to=39, width=3, textvariable=self.start_y).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row2, text="Goal (x,y)").pack(side=tk.LEFT)
        ttk.Spinbox(row2, from_=0, to=39, width=3, textvariable=self.goal_x).pack(side=tk.LEFT, padx=2)
        ttk.Spinbox(row2, from_=0, to=39, width=3, textvariable=self.goal_y).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row2, text="CPs x,y;...").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.cp_text, width=24).pack(side=tk.LEFT, padx=4)

        ttk.Button(row2, text="Load JSON…", command=self.load_json).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Save JSON", command=self.save_json).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Clear walls", command=self.clear_walls).pack(side=tk.RIGHT, padx=4)

    def _build_canvas(self):
        wrap = ttk.Frame(self.container, padding=8)
        wrap.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(wrap, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw())

        hint = ttk.Label(
            self.container,
            text="Click cạnh giữa 2 ô để chặn / bỏ chặn. Góc map = tường cứng (biên).",
            padding=(8, 0),
        )
        hint.pack(fill=tk.X)

    def _build_status(self):
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.container, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W, padding=4).pack(
            fill=tk.X, side=tk.BOTTOM
        )

    def _noop(self):
        pass

    def cell_px(self, x, y):
        px = MARGIN + x * CELL
        py = MARGIN + (self.height - 1 - y) * CELL
        return px, py

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
        self.redraw()
        self.status.set("Map %d×%d" % (w, h))

    def _edge_valid(self, x, y, d):
        if not is_valid(x, y, self.width, self.height):
            return False
        nx, ny = neighbor_xy(x, y, d)
        return is_valid(nx, ny, self.width, self.height)

    def _parse_checkpoints(self):
        text = self.cp_text.get().strip()
        if not text:
            return []
        out = []
        for part in text.split(";"):
            part = part.strip()
            if not part:
                continue
            xs, ys = part.split(",")
            out.append([int(xs.strip()), int(ys.strip())])
        return out

    def _load_checkpoints(self, cps):
        self.cp_text.set(";".join("%d,%d" % (c[0], c[1]) for c in cps))

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
        if edge is None:
            return
        if edge in self.walls:
            self.walls.remove(edge)
        else:
            self.walls.add(edge)
        self.redraw()
        x, y, d = edge
        blocked = edge in self.walls
        self.status.set("Edge (%d,%d) %s → %s" % (x, y, d, "blocked" if blocked else "open"))

    def pick_edge(self, cx, cy):
        best = None
        best_d = EDGE_HIT + 1
        for y in range(self.height):
            for x in range(self.width):
                px, py = self.cell_px(x, y)
                candidates = [
                    (x, y, "N", px, py, px + CELL, py),
                    (x, y, "E", px + CELL, py, px + CELL, py + CELL),
                    (x, y, "S", px, py + CELL, px + CELL, py + CELL),
                    (x, y, "W", px, py, px, py + CELL),
                ]
                for ex, ey, d, x1, y1, x2, y2 in candidates:
                    if not self._edge_valid(ex, ey, d):
                        continue
                    dist = self._point_seg_dist(cx, cy, x1, y1, x2, y2)
                    if dist < best_d:
                        best_d = dist
                        best = (ex, ey, d)
        return best if best_d <= EDGE_HIT else None

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

    def redraw(self):
        c = self.canvas
        c.delete("all")
        cw = max(self.width * CELL + 2 * MARGIN, 200)
        ch = max(self.height * CELL + 2 * MARGIN, 200)
        c.config(scrollregion=(0, 0, cw, ch))

        start = (self.start_x.get(), self.start_y.get())
        goal = (self.goal_x.get(), self.goal_y.get())
        cps = {tuple(cp) for cp in self._parse_checkpoints()}

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
                    px, py, px + CELL, py + CELL, fill=fill, outline="#45475a", width=1
                )
                c.create_text(px + CELL // 2, py + CELL // 2, text="%d,%d" % (x, y), fill="#cdd6f4", font=("", 8))

        for y in range(self.height):
            for x in range(self.width):
                px, py = self.cell_px(x, y)
                for d, x1, y1, x2, y2 in [
                    ("N", px, py, px + CELL, py),
                    ("E", px + CELL, py, px + CELL, py + CELL),
                    ("S", px, py + CELL, px + CELL, py + CELL),
                    ("W", px, py, px, py + CELL),
                ]:
                    if not self._edge_valid(x, y, d):
                        c.create_line(x1, y1, x2, y2, fill="#11111b", width=4)
                        continue
                    key = (x, y, d)
                    color = "#f38ba8" if key in self.walls else "#585b70"
                    width = 5 if key in self.walls else 2
                    c.create_line(x1, y1, x2, y2, fill=color, width=width)

    def run(self):
        if self._standalone:
            self.root.mainloop()


def run_app(parent=None, root=None, on_saved=None):
    app = MapEditorApp(parent=parent, root=root, on_saved=on_saved)
    if parent is None:
        app.run()
    return app
