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
    MAP_ROOT,
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
from Ui_app.ui_scale import checkpoint_label_font, checkpoint_label_inset, configure_window, init as init_ui_scale, px, font

from app_icon import apply_app_icon

class MapEditorApp:
    def __init__(self, parent=None, root=None, on_saved=None):
        if parent is None:
            self.root = tk.Tk()
            self.root.title("SS26 Map Editor")
            apply_app_icon(self.root)
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
        self._train_list_selected = None
        self._infer_list_selected = None
        self._map_list_select_bg = {}
        self._map_list_wheel_cb = {}
        self._map_list_drag_cb = {}
        self._suppress_list_events = False
        self._active_list_kind = None
        self._side_panel_width = None
        self._preserve_side_panel_width = False

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

        row2 = ttk.Frame(self.container, padding=(8, 0, 8, 8))
        row2.pack(fill=tk.X)

        ttk.Label(row2, textvariable=self._pos_label).pack(side=tk.LEFT, padx=(0, 12))

        self.btn_add_cp = ttk.Button(row2, text="Thêm checkpoint", command=self.add_checkpoint)
        self.btn_add_cp.pack(side=tk.LEFT, padx=(0, 4))
        self.btn_remove_cp = ttk.Button(row2, text="Xóa checkpoint", command=self.remove_selected_checkpoint)
        self.btn_remove_cp.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(row2, text="Lưu infer", command=self.save_infer).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Lưu train", command=self.save_train).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Load map", command=self.load_map).pack(side=tk.RIGHT, padx=4)
        ttk.Button(row2, text="Clear walls", command=self.clear_walls).pack(side=tk.RIGHT, padx=4)

        self._update_pos_label()

    def _build_workspace(self):
        self._workspace = ttk.Frame(self.container)
        self._workspace.pack(fill=tk.BOTH, expand=True)
        self._workspace.rowconfigure(0, weight=1)
        self._workspace.columnconfigure(0, weight=1)

        try:
            pane_bg = ttk.Style().lookup("TFrame", "background")
        except tk.TclError:
            pane_bg = "#f0f0f0"

        self._paned = tk.PanedWindow(
            self._workspace,
            orient=tk.HORIZONTAL,
            sashwidth=px(6),
            sashrelief=tk.RAISED,
            opaqueresize=False,
            bg=pane_bg,
            bd=0,
            showhandle=False,
        )
        self._paned.pack(fill=tk.BOTH, expand=True)
        self._paned.bind("<ButtonRelease-1>", self._on_paned_resize)

        self._canvas_wrap = ttk.Frame(self._paned, padding=px(8))
        self.canvas = tk.Canvas(self._canvas_wrap, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self._canvas_wrap.bind("<Configure>", self._on_resize_event)
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<Delete>", self._on_delete_key)
        self.root.bind("<BackSpace>", self._on_delete_key)

        side = ttk.LabelFrame(self._paned, text="List map", padding=px(6))
        self._side_panel = side
        self._side_panel.bind("<Configure>", self._on_side_panel_configure, add="+")
        side.columnconfigure(0, weight=1)
        side.rowconfigure(1, weight=1)
        side.rowconfigure(3, weight=1)

        ttk.Label(side, text="Train Map").grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        train_wrap = self._build_map_scroll_list(side, "train")
        train_wrap.grid(row=1, column=0, sticky="nsew", pady=(0, px(8)))

        ttk.Label(side, text="Inference Map").grid(row=2, column=0, sticky=tk.W, pady=(0, 2))
        infer_wrap = self._build_map_scroll_list(side, "infer")
        infer_wrap.grid(row=3, column=0, sticky="nsew")

        self._paned.add(self._canvas_wrap, minsize=px(360), stretch="always")
        self._paned.add(side, minsize=px(240), stretch="always")
        self.root.after_idle(self._restore_paned_layout)

    def _on_paned_resize(self, _event=None):
        self._remember_paned_layout()
        try:
            self.root.after_idle(self.redraw)
        except Exception:
            pass

    def _on_side_panel_configure(self, _event=None):
        self._remember_paned_layout()

    def _remember_paned_layout(self, force=False):
        try:
            if self._preserve_side_panel_width and not force:
                return
            if hasattr(self, "_side_panel") and self._side_panel.winfo_ismapped():
                w = int(self._side_panel.winfo_width())
                if w > 1:
                    self._side_panel_width = w
        except (tk.TclError, ValueError):
            pass

    def _restore_paned_layout(self):
        try:
            if self._side_panel_width is None:
                return
            total_w = int(self._paned.winfo_width())
            if total_w <= 1:
                return
            sash_w = int(self._paned.cget("sashwidth") or 0)
            min_left = px(360)
            min_right = px(240)
            max_left = total_w - sash_w - min_right
            if max_left <= min_left:
                return
            target = total_w - sash_w - int(self._side_panel_width)
            target = max(min_left, min(max_left, target))
            self._paned.sash_place(0, target, 0)
        except (tk.TclError, ValueError):
            pass
        finally:
            self._preserve_side_panel_width = False

    def _build_map_scroll_list(self, parent, kind):
        wrap = ttk.Frame(parent)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        canvas = tk.Canvas(wrap, highlightthickness=0, borderwidth=0, height=1)
        scroll = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        drag_state = {"active": False, "moved": False, "x": 0, "y": 0}

        def _sync_viewport(_event=None):
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)

        def _on_wrap_configure(event):
            scroll_w = scroll.winfo_width() or px(16)
            inner_w = max(1, event.width - scroll_w)
            canvas.itemconfigure(win, width=inner_w)
            if event.height > 1:
                canvas.configure(height=event.height)

        def _on_wheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            return "break"

        def _canvas_coords(event):
            return event.x, event.y

        def _start_drag(event):
            drag_state["active"] = True
            drag_state["moved"] = False
            drag_state["x"] = event.x
            drag_state["y"] = event.y
            cx, cy = _canvas_coords(event)
            canvas.scan_mark(cx, cy)

        def _drag_motion(event):
            if not drag_state["active"]:
                return
            if abs(event.x - drag_state["x"]) + abs(event.y - drag_state["y"]) > 3:
                drag_state["moved"] = True
            if drag_state["moved"]:
                cx, cy = _canvas_coords(event)
                canvas.scan_dragto(cx, cy, gain=1)
                return "break"

        def _end_drag(_event=None):
            drag_state["active"] = False
            drag_state["moved"] = False

        def _bind_wheel(widget):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                widget.bind(seq, _on_wheel, add="+")

        def _bind_drag(widget):
            widget.bind("<ButtonPress-1>", _start_drag, add="+")
            widget.bind("<B1-Motion>", _drag_motion, add="+")
            widget.bind("<ButtonRelease-1>", _end_drag, add="+")

        inner.bind("<Configure>", _sync_viewport)
        wrap.bind("<Configure>", _on_wrap_configure)
        _bind_wheel(canvas)
        _bind_wheel(inner)
        _bind_wheel(wrap)
        _bind_drag(canvas)
        _bind_drag(inner)
        _bind_drag(wrap)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.config(command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        if kind == "train":
            self._train_list_canvas = canvas
            self._train_list_inner = inner
            self._train_list_rows = {}
            select_bg = "#a6e3a1"
        else:
            self._infer_list_canvas = canvas
            self._infer_list_inner = inner
            self._infer_list_rows = {}
            select_bg = "#89b4fa"
        self._map_list_wheel_cb[kind] = _on_wheel
        self._map_list_drag_cb[kind] = {
            "start": _start_drag,
            "motion": _drag_motion,
            "end": _end_drag,
        }
        self._map_list_select_bg[kind] = select_bg
        return wrap

    def _map_list_inner(self, kind):
        return self._train_list_inner if kind == "train" else self._infer_list_inner

    def _map_list_rows(self, kind):
        return self._train_list_rows if kind == "train" else self._infer_list_rows

    def _map_list_selected(self, kind):
        return self._train_list_selected if kind == "train" else self._infer_list_selected

    def _set_map_list_selected(self, kind, path):
        path = os.path.abspath(path) if path else None
        if kind == "train":
            self._train_list_selected = path
        else:
            self._infer_list_selected = path

    def _clear_other_map_selection(self, kind):
        other = "infer" if kind == "train" else "train"
        if self._map_list_selected(other):
            self._set_map_list_selected(other, None)
            self._highlight_map_list_rows(other)

    def _rebuild_map_list(self, kind, paths, select_path=None):
        paths = [os.path.abspath(p) for p in paths]
        inner = self._map_list_inner(kind)
        rows = self._map_list_rows(kind)
        rows.clear()
        for child in inner.winfo_children():
            child.destroy()

        selected = os.path.abspath(select_path) if select_path else None
        if selected not in paths:
            selected = None
        if selected is None and paths:
            prev = self._map_list_selected(kind)
            if prev and os.path.abspath(prev) in paths:
                selected = os.path.abspath(prev)

        for path in paths:
            self._add_map_list_row(kind, path, path == selected)

        if selected:
            self._set_map_list_selected(kind, selected)
        else:
            cur = self._map_list_selected(kind)
            if cur and os.path.abspath(cur) not in paths:
                self._set_map_list_selected(kind, None)
        self._sync_map_list_scroll(kind)

    def _map_list_canvas(self, kind):
        return self._train_list_canvas if kind == "train" else self._infer_list_canvas

    def _sync_map_list_scroll(self, kind):
        canvas = self._map_list_canvas(kind)
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if bbox:
            canvas.configure(scrollregion=bbox)

    def _add_map_list_row(self, kind, path, selected=False):
        path = os.path.abspath(path)
        inner = self._map_list_inner(kind)
        rows = self._map_list_rows(kind)
        name = os.path.splitext(os.path.basename(path))[0]
        bg = self._map_list_select_bg[kind] if selected else "#313244"
        fg = "#11111b" if selected else "#cdd6f4"

        row = tk.Frame(inner, bg=bg)
        row.pack(fill=tk.X, pady=1)

        name_lbl = tk.Label(
            row,
            text=name,
            bg=bg,
            fg=fg,
            anchor=tk.W,
            font=font(10),
            padx=px(6),
            pady=px(4),
            cursor="hand2",
        )
        name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        del_btn = tk.Button(
            row,
            text="🗑",
            bg=bg,
            fg="#f38ba8" if not selected else "#c9184a",
            activebackground=bg,
            activeforeground="#eba0ac",
            relief=tk.FLAT,
            bd=0,
            font=font(11),
            cursor="hand2",
            padx=px(4),
            pady=px(2),
        )
        del_btn.pack(side=tk.RIGHT)

        def _activate(_event=None):
            if self._suppress_list_events:
                return
            other = "infer" if kind == "train" else "train"
            self._set_map_list_selected(kind, path)
            self._clear_other_map_selection(kind)
            self._active_list_kind = kind
            self._highlight_map_list_rows(kind)
            self._load_from_path(path, kind, from_list=True)

        def _delete(_event=None):
            self._delete_map_path(kind, path)

        canvas = self._map_list_canvas(kind)
        row_drag = {"active": False, "moved": False, "x": 0, "y": 0}

        def _row_press(event):
            row_drag["active"] = True
            row_drag["moved"] = False
            row_drag["x"] = event.x_root
            row_drag["y"] = event.y_root
            cx = event.x_root - canvas.winfo_rootx()
            cy = event.y_root - canvas.winfo_rooty()
            canvas.scan_mark(cx, cy)

        def _row_motion(event):
            if not row_drag["active"]:
                return
            if abs(event.x_root - row_drag["x"]) + abs(event.y_root - row_drag["y"]) > 4:
                row_drag["moved"] = True
            if row_drag["moved"]:
                cx = event.x_root - canvas.winfo_rootx()
                cy = event.y_root - canvas.winfo_rooty()
                canvas.scan_dragto(cx, cy, gain=1)
                return "break"

        def _row_release(event):
            if not row_drag["active"]:
                return
            moved = row_drag["moved"]
            row_drag["active"] = False
            row_drag["moved"] = False
            if moved or event.widget is del_btn:
                return "break"
            _activate()

        for widget in (row, name_lbl):
            widget.bind("<ButtonPress-1>", _row_press)
            widget.bind("<B1-Motion>", _row_motion)
            widget.bind("<ButtonRelease-1>", _row_release)
        wheel_cb = self._map_list_wheel_cb.get(kind)
        if wheel_cb:
            for widget in (row, name_lbl, del_btn):
                for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    widget.bind(seq, wheel_cb, add="+")
        del_btn.configure(command=_delete)
        rows[path] = row

    def _highlight_map_list_rows(self, kind):
        selected = self._map_list_selected(kind)
        rows = self._map_list_rows(kind)
        for path, row in rows.items():
            is_sel = path == selected
            bg = self._map_list_select_bg[kind] if is_sel else "#313244"
            fg = "#11111b" if is_sel else "#cdd6f4"
            row.configure(bg=bg)
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=bg, fg=fg)
                elif isinstance(child, tk.Button):
                    child.configure(
                        bg=bg,
                        fg="#c9184a" if is_sel else "#f38ba8",
                        activebackground=bg,
                    )

    def refresh_map_lists(self, kind=None, select_path=None):
        """Đọc lại map/train + map/infer; giữ selection nếu file còn tồn tại."""
        self._remember_paned_layout(force=True)
        self._preserve_side_panel_width = True
        prev_train = self._selected_map_path("train")
        prev_infer = self._selected_map_path("infer")
        if select_path:
            if self._kind_from_path(select_path) == "infer":
                prev_infer = select_path
            else:
                prev_train = select_path

        self._suppress_list_events = True
        try:
            self._train_map_paths = [os.path.abspath(p) for p in list_map_files("train")]
            self._infer_map_paths = [os.path.abspath(p) for p in list_map_files("infer")]

            train_select = prev_train
            infer_select = prev_infer

            self._rebuild_map_list("train", self._train_map_paths, train_select)
            self._rebuild_map_list("infer", self._infer_map_paths, infer_select)
        finally:
            self._suppress_list_events = False
        self.root.after_idle(self._restore_paned_layout)

    def _selected_map_path(self, kind):
        return self._map_list_selected(kind)

    def _select_in_list(self, kind, path):
        if not path:
            return
        paths = self._train_map_paths if kind == "train" else self._infer_map_paths
        abs_path = os.path.abspath(path)
        if abs_path not in paths:
            base = os.path.basename(path)
            match = next((p for p in paths if os.path.basename(p) == base), None)
            if match is None:
                return
            abs_path = match
        self._set_map_list_selected(kind, abs_path)
        self._highlight_map_list_rows(kind)

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
        map_name = self._ask_map_name(kind)
        if map_name is None:
            return
        self.map_name.set(map_name)
        spec = self.current_spec(kind=kind)
        try:
            path = save_map_json(spec, kind=kind)
            path = os.path.abspath(path)
        except (OSError, ValueError, tk.TclError) as e:
            messagebox.showerror("Save", str(e))
            return
        self.map_name.set(map_name)
        self.status.set("Saved: %s" % path)
        self._notify_maps_changed(kind, path)

    def save_train(self):
        self._save_map("train")

    def save_infer(self):
        self._save_map("infer")

    def _ask_map_name(self, kind):
        default_name = (self.map_name.get() or "").strip()
        if not default_name:
            default_name = "custom_%s" % ("train" if kind == "train" else "infer")

        result = {"value": None}
        dlg = tk.Toplevel(self.root)
        dlg.title("Đặt tên map")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        body = ttk.Frame(dlg, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text="Tên map %s:" % ("train" if kind == "train" else "infer")).pack(
            anchor=tk.W, pady=(0, 6)
        )
        name_var = tk.StringVar(value=default_name)
        entry = ttk.Entry(body, textvariable=name_var, width=28)
        entry.pack(fill=tk.X)
        entry.focus_set()
        entry.selection_range(0, tk.END)

        hint = ttk.Label(body, text="Enter để tạo map, Esc để hủy.")
        hint.pack(anchor=tk.W, pady=(6, 0))

        btn_row = ttk.Frame(body)
        btn_row.pack(fill=tk.X, pady=(10, 0))

        def _confirm(_event=None):
            raw = name_var.get().strip()
            if not raw:
                messagebox.showerror("Lưu map", "Tên map không được để trống.")
                return
            result["value"] = raw
            dlg.destroy()

        def _cancel(_event=None):
            dlg.destroy()

        ttk.Button(btn_row, text="Hủy", command=_cancel).pack(side=tk.RIGHT)
        ttk.Button(btn_row, text="Tạo", command=_confirm).pack(side=tk.RIGHT, padx=(0, 8))

        dlg.bind("<Return>", _confirm)
        dlg.bind("<Escape>", _cancel)
        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        dlg.update_idletasks()
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        ry = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry("+%d+%d" % (max(0, rx), max(0, ry)))
        self.root.wait_window(dlg)
        return result["value"]

    def load_map(self):
        os.makedirs(TRAIN_MAPS_DIR, exist_ok=True)
        os.makedirs(INFER_MAPS_DIR, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Load map",
            initialdir=MAP_ROOT,
            filetypes=[("Map files", "map_*.json"), ("All", "*.json")],
        )
        if not path:
            return
        kind = self._kind_from_path(path)
        self._load_from_path(path, kind, from_list=True)

    def _confirm_yes_no(self, title, message):
        """Hộp xác nhận Tk — không dùng messagebox hệ thống (tránh tiếng beep)."""
        result = {"value": False}
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        ttk.Label(dlg, text=message, padding=12, wraplength=px(320), justify=tk.LEFT).pack()
        btn_row = ttk.Frame(dlg, padding=(12, 0, 12, 12))
        btn_row.pack(fill=tk.X)

        def _yes():
            result["value"] = True
            dlg.destroy()

        def _no():
            dlg.destroy()

        ttk.Button(btn_row, text="Không", command=_no).pack(side=tk.RIGHT)
        ttk.Button(btn_row, text="Có", command=_yes).pack(side=tk.RIGHT, padx=(8, 0))
        dlg.protocol("WM_DELETE_WINDOW", _no)
        dlg.bind("<Escape>", lambda _e: _no())

        dlg.update_idletasks()
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        ry = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry("+%d+%d" % (max(0, rx), max(0, ry)))
        self.root.wait_window(dlg)
        return result["value"]

    def _delete_map_path(self, kind, path):
        if not path or not os.path.isfile(path):
            messagebox.showerror("Lỗi", "Không tìm thấy file bản đồ.")
            return
        filename = os.path.basename(path)
        if not self._confirm_yes_no(
            "Xác nhận xóa",
            "Bạn có chắc chắn muốn xóa bản đồ '%s' không?" % filename,
        ):
            return
        try:
            os.remove(path)
        except OSError as exc:
            messagebox.showerror("Lỗi", "Không thể xóa file: %s" % exc)
            return
        if self._map_list_selected(kind) == os.path.abspath(path):
            self._set_map_list_selected(kind, None)
        self.status.set("Đã xóa: %s" % filename)
        self._notify_maps_changed(kind)

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
        cps = [tuple(cp) for cp in self.checkpoints if len(cp) >= 2]
        cp_index = {cp: i for i, cp in enumerate(cps)}
        sel_cell = self._selection_cell()

        for y in range(self.height):
            for x in range(self.width):
                px, py = self.cell_px(x, y)
                fill = "#313244"
                if (x, y) == start:
                    fill = "#a6e3a1"
                elif (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cp_index:
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
                if (x, y) in cp_index:
                    inset = checkpoint_label_inset(cell)
                    c.create_text(
                        px + cell - inset,
                        py + inset,
                        text="%d" % (cp_index[(x, y)] + 1),
                        fill="#11111b",
                        font=checkpoint_label_font(cell),
                        anchor=tk.NE,
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
