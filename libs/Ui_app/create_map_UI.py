"""
UI tạo / chỉnh map — grid, bấm cạnh để chặn / mở, lưu train hoặc infer.
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
from Ui_app.map_layout import apply_fixed_canvas, avail_from_wrap, fit_grid_layout
from Ui_app.ui_scale import configure_window, init as init_ui_scale, px, font, text_lines


class MapEditorApp:
    def __init__(self, parent=None, root=None, on_saved=None):
        if parent is None:
            self.root = tk.Tk()
            self.root.title("SS26 Map Editor")
            init_ui_scale(self.root)
            configure_window(self.root, width=1000, height=700, min_width=720, min_height=560)
            self.container = self.root
            self._standalone = True
        else:
            self.root = root or parent.winfo_toplevel()
            self.container = parent
            self._standalone = False

        self._on_saved = on_saved

        self.width = 5
        self.height = 5
        self.walls = set()
        self.map_name = tk.StringVar(value="custom_01")
        self.start_x = tk.IntVar(value=0)
        self.start_y = tk.IntVar(value=0)
        self.goal_x = tk.IntVar(value=4)
        self.goal_y = tk.IntVar(value=4)
        self.checkpoints = []
        self._selection = None  # ('start',) | ('goal',) | ('cp', index)
        self._await_new_cp = False
        self._pos_label = tk.StringVar(value="")
        self._cell = 52
        self._offset_x = 0
        self._offset_y = 0
        self._edge_hit = 10
        self._last_wrap_size = None
        self._resize_after_id = None
        self._train_map_paths = []
        self._infer_map_paths = []
        self._suppress_list_events = False
        self._active_list_kind = None

        self._build_toolbar()
        self._build_workspace()
        self._build_status()
        self.apply_size()
        self.refresh_map_lists()
        self.root.after_idle(self.redraw)

    _MAX_TRAIN = 5
    _MAX_INFER = 10

    @staticmethod
    def _max_size_for_kind(kind):
        return MapEditorApp._MAX_TRAIN if kind == "train" else MapEditorApp._MAX_INFER

    @staticmethod
    def _kind_from_path(path):
        norm = os.path.abspath(path).replace("\\", "/")
        if "/map/infer/" in norm:
            return "infer"
        return "train"

    def _build_toolbar(self):
        bar = ttk.Frame(self.container, padding=8)
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="Width").grid(row=0, column=0, padx=(0, 4))
        self.spin_w = ttk.Spinbox(bar, from_=1, to=self._MAX_INFER, width=4, command=self._noop)
        self.spin_w.set(str(self.width))
        self.spin_w.grid(row=0, column=1, padx=(0, 12))

        ttk.Label(bar, text="Height").grid(row=0, column=2, padx=(0, 4))
        self.spin_h = ttk.Spinbox(bar, from_=1, to=self._MAX_INFER, width=4)
        self.spin_h.set(str(self.height))
        self.spin_h.grid(row=0, column=3, padx=(0, 12))

        self.btn_apply_size = ttk.Button(bar, text="Apply size", command=self.apply_size)
        self.btn_apply_size.grid(row=0, column=4, padx=4)

        ttk.Separator(bar, orient=tk.VERTICAL).grid(row=0, column=5, sticky="ns", padx=12)

        ttk.Label(bar, text="Name").grid(row=0, column=6, padx=(0, 4))
        ttk.Entry(bar, textvariable=self.map_name, width=14).grid(row=0, column=7, padx=(0, 12))

        row2 = ttk.Frame(self.container, padding=(8, 0, 8, 8))
        row2.pack(fill=tk.X)

        ttk.Label(row2, textvariable=self._pos_label).pack(side=tk.LEFT, padx=(0, 12))

        self.btn_add_cp = ttk.Button(row2, text="Thêm checkpoint", command=self.add_checkpoint)
        self.btn_add_cp.pack(side=tk.LEFT, padx=(0, 4))
        self.btn_remove_cp = ttk.Button(row2, text="Xóa checkpoint", command=self.remove_selected_checkpoint)
        self.btn_remove_cp.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(row2, text="Xóa bản đồ…", command=self.delete_map).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Lưu infer", command=self.save_infer).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Lưu train", command=self.save_train).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Load infer map", command=self.load_infer_map).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Load train map", command=self.load_train_map).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Clear walls", command=self.clear_walls).pack(side=tk.RIGHT, padx=4)

        self._update_pos_label()

    def _build_workspace(self):
        self._workspace = ttk.Frame(self.container)
        self._workspace.pack(fill=tk.BOTH, expand=True)
        self._workspace.columnconfigure(0, weight=2)
        self._workspace.columnconfigure(1, weight=1, minsize=px(320))
        self._workspace.rowconfigure(0, weight=1)

        self._canvas_wrap = ttk.Frame(self._workspace, padding=px(8))
        self._canvas_wrap.grid(row=0, column=0, sticky="nsew")

        self.canvas = tk.Canvas(self._canvas_wrap, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self._canvas_wrap.bind("<Configure>", self._on_resize_event)
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<Delete>", self._on_delete_key)
        self.root.bind("<BackSpace>", self._on_delete_key)

        side = ttk.LabelFrame(self._workspace, text="List map", padding=px(6))
        side.grid(row=0, column=1, sticky="nsew", padx=(0, px(8)), pady=px(8))
        side.columnconfigure(0, weight=1)
        side.rowconfigure(1, weight=1)
        side.rowconfigure(3, weight=1)

        ttk.Label(side, text="Train Map").grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        train_wrap = ttk.Frame(side)
        train_wrap.grid(row=1, column=0, sticky="nsew", pady=(0, px(8)))
        train_wrap.columnconfigure(0, weight=1)
        train_wrap.rowconfigure(0, weight=1)
        scroll_t = ttk.Scrollbar(train_wrap, orient=tk.VERTICAL)
        self.train_map_list = tk.Listbox(
            train_wrap,
            height=text_lines(14),
            activestyle=tk.DOTBOX,
            exportselection=False,
            font=font(10),
            width=28,
            selectbackground="#a6e3a1",
            selectforeground="#11111b",
        )
        scroll_t.config(command=self.train_map_list.yview)
        self.train_map_list.config(yscrollcommand=scroll_t.set)
        self.train_map_list.grid(row=0, column=0, sticky="nsew")
        scroll_t.grid(row=0, column=1, sticky="ns")
        self.train_map_list.bind("<<ListboxSelect>>", lambda _e: self._on_map_list_select("train"))

        ttk.Label(side, text="Inference Map").grid(row=2, column=0, sticky=tk.W, pady=(0, 2))
        infer_wrap = ttk.Frame(side)
        infer_wrap.grid(row=3, column=0, sticky="nsew")
        infer_wrap.columnconfigure(0, weight=1)
        infer_wrap.rowconfigure(0, weight=1)
        scroll_i = ttk.Scrollbar(infer_wrap, orient=tk.VERTICAL)
        self.infer_map_list = tk.Listbox(
            infer_wrap,
            height=text_lines(14),
            activestyle=tk.DOTBOX,
            exportselection=False,
            font=font(10),
            width=28,
            selectbackground="#89b4fa",
            selectforeground="#11111b",
        )
        scroll_i.config(command=self.infer_map_list.yview)
        self.infer_map_list.config(yscrollcommand=scroll_i.set)
        self.infer_map_list.grid(row=0, column=0, sticky="nsew")
        scroll_i.grid(row=0, column=1, sticky="ns")
        self.infer_map_list.bind("<<ListboxSelect>>", lambda _e: self._on_map_list_select("infer"))

    def refresh_map_lists(self, kind=None, select_path=None):
        """Đọc lại map/train + map/infer; giữ selection nếu file còn tồn tại."""
        prev_train = self._selected_map_path("train")
        prev_infer = self._selected_map_path("infer")
        if select_path:
            if self._kind_from_path(select_path) == "infer":
                prev_infer = select_path
            else:
                prev_train = select_path

        self._suppress_list_events = True
        try:
            self._train_map_paths = list_map_files("train")
            self.train_map_list.delete(0, tk.END)
            for path in self._train_map_paths:
                self.train_map_list.insert(tk.END, os.path.basename(path))

            self._infer_map_paths = list_map_files("infer")
            self.infer_map_list.delete(0, tk.END)
            for path in self._infer_map_paths:
                self.infer_map_list.insert(tk.END, os.path.basename(path))

            self._select_in_list("train", prev_train)
            self._select_in_list("infer", prev_infer)
        finally:
            self._suppress_list_events = False

    def _selected_map_path(self, kind):
        lb = self.train_map_list if kind == "train" else self.infer_map_list
        paths = self._train_map_paths if kind == "train" else self._infer_map_paths
        sel = lb.curselection()
        if not sel or sel[0] >= len(paths):
            return None
        return paths[sel[0]]

    def _select_in_list(self, kind, path):
        if not path:
            return
        lb = self.train_map_list if kind == "train" else self.infer_map_list
        paths = self._train_map_paths if kind == "train" else self._infer_map_paths
        try:
            idx = paths.index(os.path.abspath(path))
        except ValueError:
            base = os.path.basename(path)
            idx = next((i for i, p in enumerate(paths) if os.path.basename(p) == base), None)
            if idx is None:
                return
        lb.selection_clear(0, tk.END)
        lb.selection_set(idx)
        lb.see(idx)

    def _on_map_list_select(self, kind):
        if self._suppress_list_events:
            return
        paths = self._train_map_paths if kind == "train" else self._infer_map_paths
        lb = self.train_map_list if kind == "train" else self.infer_map_list
        sel = lb.curselection()
        if not sel or sel[0] >= len(paths):
            return
        other = self.infer_map_list if kind == "train" else self.train_map_list
        other.selection_clear(0, tk.END)
        self._active_list_kind = kind
        self._load_from_path(paths[sel[0]], kind, from_list=True)

    def _notify_maps_changed(self, kind, path=None):
        self.refresh_map_lists(kind=kind, select_path=path)
        if self._on_saved:
            try:
                self._on_saved(kind, path)
            except Exception:
                pass

    def _load_from_path(self, path, kind, from_list=False):
        try:
            spec = load_map_json(path)
            w = int(spec.get("width", 0))
            h = int(spec.get("height", 0))
            max_val = self._max_size_for_kind(kind)
            if w > max_val or h > max_val:
                label = "train" if kind == "train" else "infer"
                messagebox.showerror(
                    "Load",
                    "Map %s chỉ được tối đa %dx%d." % (label, max_val, max_val),
                )
                return
            self.load_spec(spec)
            if from_list:
                self._select_in_list(kind, path)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            messagebox.showerror("Load", str(e))

    def _on_resize_event(self, event):
        size = (event.width, event.height)
        if size[0] < 2 or size[1] < 2 or size == self._last_wrap_size:
            return
        self._last_wrap_size = size
        if self._resize_after_id:
            self._canvas_wrap.after_cancel(self._resize_after_id)
        self._resize_after_id = self._canvas_wrap.after(50, self._throttled_redraw)

    def _throttled_redraw(self):
        self._resize_after_id = None
        self.redraw()

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
        """Phóng map tối đa trong khung, căn giữa."""
        aw, ah = avail_from_wrap(self._canvas_wrap, min_w=200, min_h=160)
        cell, ox, oy, cw, ch = fit_grid_layout(self.width, self.height, aw, ah)
        self._cell = cell
        self._offset_x = ox
        self._offset_y = oy
        self._edge_hit = max(px(6), min(px(18), self._cell // 4))
        apply_fixed_canvas(self.canvas, cw, ch)
        return cw, ch

    def apply_size(self):
        try:
            w = int(self.spin_w.get())
            h = int(self.spin_h.get())
        except ValueError:
            messagebox.showerror("Size", "Width / height phải là số nguyên.")
            return
        max_val = self._MAX_INFER
        if w < 1 or h < 1 or w > max_val or h > max_val:
            messagebox.showerror(
                "Size",
                "Kích thước map tối đa khi chỉnh là %dx%d (train lưu tối đa %dx%d)."
                % (max_val, max_val, self._MAX_TRAIN, self._MAX_TRAIN),
            )
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

    def current_spec(self, kind="train"):
        return spec_from_walls(
            self.width,
            self.height,
            self.walls,
            name=self.map_name.get().strip() or "custom",
            kind=kind,
            start=[self.start_x.get(), self.start_y.get()],
            goal=[self.goal_x.get(), self.goal_y.get()],
            checkpoints=self._parse_checkpoints(),
        )

    def _validate_size_for_kind(self, kind, width=None, height=None):
        w = self.width if width is None else width
        h = self.height if height is None else height
        max_val = self._max_size_for_kind(kind)
        if w < 1 or h < 1 or w > max_val or h > max_val:
            label = "train" if kind == "train" else "infer"
            messagebox.showerror(
                "Size",
                "Map %s chỉ được tối đa %dx%d (hiện tại %dx%d)."
                % (label, max_val, max_val, w, h),
            )
            return False
        return True

    def load_spec(self, spec):
        raw_name = spec.get("name", "custom")
        for pref in ("map_train_", "map_infer_"):
            if raw_name.startswith(pref):
                raw_name = raw_name[len(pref) :]
        self.map_name.set(raw_name or "custom")
        self.width = int(spec["width"])
        self.height = int(spec["height"])
        self.spin_w.set(str(self.width))
        self.spin_h.set(str(self.height))
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

    def _save_map(self, kind):
        if not self._validate_size_for_kind(kind):
            return
        spec = self.current_spec(kind=kind)
        try:
            path = save_map_json(spec, kind=kind)
            path = os.path.abspath(path)
            self.map_name.set(spec["name"])
        except (OSError, ValueError, tk.TclError) as e:
            messagebox.showerror("Save", str(e))
            return
        folder = "train" if kind == "train" else "infer"
        self.status.set("Saved: %s" % path)
        self._notify_maps_changed(kind, path)
        messagebox.showinfo("Saved", "Đã lưu vào map/%s/\n%s" % (folder, path))

    def save_train(self):
        self._save_map("train")

    def save_infer(self):
        self._save_map("infer")

    def _load_map(self, kind):
        initial = TRAIN_MAPS_DIR if kind == "train" else INFER_MAPS_DIR
        os.makedirs(initial, exist_ok=True)
        label = "train" if kind == "train" else "infer"
        path = filedialog.askopenfilename(
            title="Load %s map" % label,
            initialdir=initial,
            filetypes=[("Map files", "map_*.json"), ("All", "*.json")],
        )
        if not path:
            return
        self._load_from_path(path, kind, from_list=True)

    def load_train_map(self):
        self._load_map("train")

    def load_infer_map(self):
        self._load_map("infer")

    def delete_map(self):
        path = filedialog.askopenfilename(
            title="Xóa map",
            initialdir=TRAIN_MAPS_DIR,
            filetypes=[("Map files", "map_*.json"), ("All", "*.json")],
        )
        if not path:
            return
        kind = self._kind_from_path(path)
        filename = os.path.basename(path)
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa bản đồ '{filename}' không?",
            icon="warning",
        )
        if not confirm:
            return
        try:
            os.remove(path)
            messagebox.showinfo("Đã xóa", f"Đã xóa thành công bản đồ '{filename}'!")
            self._notify_maps_changed(kind, path)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xóa file: {str(e)}")

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
        c.addtag_all("old")
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
                text="Bấm ô để đặt checkpoint mới",
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
        c.delete("old")

    def run(self):
        if self._standalone:
            self.root.mainloop()


def run_app(parent=None, root=None, on_saved=None):
    app = MapEditorApp(parent=parent, root=root, on_saved=on_saved)
    if parent is None:
        app.run()
    return app
