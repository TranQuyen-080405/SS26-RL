"""
UI chọn Train hoặc Infer — map đọc từ map/train/ và map/infer/.
View: Log text hoặc bản đồ (preview + animation train/infer).
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SIM = os.path.join(_ROOT, "Simulation")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from map.map_io import list_map_files, build_sim_map_from_file
from Ui_app.map_view import SimMapCanvas
from Ui_app.ui_widgets import SegmentGroup, box_button, style_train_treeview, train_map_mark, train_row_tags


class TextRedirector:
    def __init__(self, widget, root):
        self.widget = widget
        self.root = root

    def write(self, text):
        if not text:
            return
        self.root.after(0, lambda: self._append(text))

    def flush(self):
        pass

    def _append(self, text):
        self.widget.configure(state=tk.NORMAL)
        at_bottom = self.widget.yview()[1] >= 0.98
        self.widget.insert(tk.END, text)
        if at_bottom:
            self.widget.see(tk.END)
        self.widget.configure(state=tk.DISABLED)


class RlApp:
    def __init__(self, parent=None, root=None):
        if parent is None:
            self.root = tk.Tk()
            self.root.title("SS26 RL — Train / Infer")
            self.root.minsize(720, 560)
            self.container = self.root
            self._standalone = True
        else:
            self.root = root or parent.winfo_toplevel()
            self.container = parent
            self._standalone = False

        self.mode = tk.StringVar(value="train")
        self.view = tk.StringVar(value="log")
        self.episodes = tk.IntVar(value=10000)
        self.step_delay = tk.StringVar(value="200")
        self.checkpoint_var = tk.StringVar(value="(mới)")
        self.export_policy_var = tk.StringVar(value="policy")
        self.infer_policy_var = tk.StringVar(value="policy.bin")
        self._running = False
        self._stop_requested = False
        self._map_paths = []
        self._train_rows = []
        self._anim_after_id = None
        self._ui_done = threading.Event()
        self.train_map_mode = tk.StringVar(value="random")
        self._drag_src_iid = None
        self._eps_entry = None
        self._eps_edit_iid = None

        self._build_toolbar()
        self._build_checkpoint_bar()
        self._build_infer_policy_bar()
        self._build_workspace()
        self._build_map_list()
        self._build_actions()
        self.mode.trace_add("write", lambda *_: self._on_mode_change())
        self.view.trace_add("write", lambda *_: self._on_view_change())
        self._on_mode_change()

    def _build_toolbar(self):
        bar = ttk.LabelFrame(self.container, text="Điều khiển chung", padding=8)
        bar.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(bar, text="Mode").grid(row=0, column=0, padx=(0, 8), sticky=tk.W)
        self.mode_group = SegmentGroup(
            bar,
            self.mode,
            [("Train", "train"), ("Infer", "infer")],
        )
        self.mode_group.grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=(0, 16))

        ttk.Separator(bar, orient=tk.VERTICAL).grid(row=0, column=3, sticky="ns", padx=8)

        ttk.Label(bar, text="View").grid(row=0, column=4, padx=(0, 8), sticky=tk.W)
        self.view_group = SegmentGroup(
            bar,
            self.view,
            [("Log", "log"), ("Map", "map")],
        )
        self.view_group.grid(row=0, column=5, columnspan=2, sticky=tk.W, padx=(0, 12))

        ttk.Label(bar, text="Episodes").grid(row=0, column=7, padx=(0, 4))
        self.spin_ep = ttk.Spinbox(bar, from_=100, to=200000, increment=100, width=8)
        self.spin_ep.set(str(self.episodes.get()))
        self.spin_ep.grid(row=0, column=8, padx=(0, 12))

        ttk.Label(bar, text="Tốc độ").grid(row=0, column=9, padx=(0, 4))
        self.delay_group = SegmentGroup(
            bar,
            self.step_delay,
            [("Nhanh", "1"), ("Chậm", "200")],
        )
        self.delay_group.grid(row=0, column=10, padx=(0, 8))

        box_button(bar, text="Refresh maps", command=self.refresh_maps, role="secondary").grid(
            row=0, column=11, padx=(4, 0)
        )

    def _build_checkpoint_bar(self):
        self.ck_frame = ttk.LabelFrame(self.container, text="Policy train", padding=(8, 6))
        row1 = ttk.Frame(self.ck_frame)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text="Nạp Q từ").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_checkpoint = ttk.Combobox(
            row1,
            textvariable=self.checkpoint_var,
            width=22,
            state="readonly",
        )
        self.combo_checkpoint.pack(side=tk.LEFT, padx=(0, 8))
        self.combo_checkpoint.bind("<<ComboboxSelected>>", self._on_checkpoint_selected)
        box_button(row1, text="Refresh Q", command=self.refresh_checkpoints, role="secondary").pack(
            side=tk.LEFT, padx=(0, 4)
        )

        row2 = ttk.Frame(self.ck_frame)
        row2.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row2, text="Lưu policy").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_export_policy = ttk.Combobox(
            row2,
            textvariable=self.export_policy_var,
            width=22,
        )
        self.combo_export_policy.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(row2, text=".bin").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(
            row2,
            text="Train mới → đặt tên file; train tiếp → có thể giữ hoặc đổi tên",
        ).pack(side=tk.LEFT, padx=8)
        self.refresh_checkpoints()

    def _build_infer_policy_bar(self):
        self.infer_policy_frame = ttk.LabelFrame(self.container, text="Policy infer", padding=(8, 6))
        ttk.Label(self.infer_policy_frame, text="Policy").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_infer_policy = ttk.Combobox(
            self.infer_policy_frame,
            textvariable=self.infer_policy_var,
            width=28,
            state="readonly",
        )
        self.combo_infer_policy.pack(side=tk.LEFT, padx=(0, 8))
        box_button(
            self.infer_policy_frame, text="Refresh list", command=self.refresh_infer_policies, role="secondary"
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(
            self.infer_policy_frame,
            text="Chọn file checkpoints/*.bin để infer",
        ).pack(side=tk.LEFT, padx=8)
        self.refresh_infer_policies()

    def refresh_infer_policies(self):
        from robot.policy_io import list_policy_bin_files

        prev = self.infer_policy_var.get()
        files = list_policy_bin_files()
        self.combo_infer_policy["values"] = files
        if prev in files:
            self.infer_policy_var.set(prev)
        elif "policy.bin" in files:
            self.infer_policy_var.set("policy.bin")
        elif files:
            self.infer_policy_var.set(files[0])
        else:
            self.infer_policy_var.set("")

    def refresh_checkpoints(self):
        from robot.policy_io import list_checkpoints, suggest_new_policy_name

        prev = self.checkpoint_var.get()
        names = list_checkpoints()
        values = ["(mới)"] + names
        self.combo_checkpoint["values"] = values
        self.combo_export_policy["values"] = names
        if prev in values:
            self.checkpoint_var.set(prev)
        elif "policy" in names:
            self.checkpoint_var.set("policy")
        else:
            self.checkpoint_var.set("(mới)")
        if self.checkpoint_var.get() == "(mới)":
            cur = self.export_policy_var.get().strip()
            if not cur or cur in names:
                self.export_policy_var.set(suggest_new_policy_name())
        elif self.export_policy_var.get().strip() not in names:
            self.export_policy_var.set(self.checkpoint_var.get())

    def _on_checkpoint_selected(self, _event=None):
        from robot.policy_io import suggest_new_policy_name

        val = self.checkpoint_var.get().strip()
        if val == "(mới)":
            self.export_policy_var.set(suggest_new_policy_name())
        else:
            self.export_policy_var.set(val)

    def _train_checkpoint_spec(self):
        val = self.checkpoint_var.get().strip()
        if not val or val == "(mới)":
            return None
        return val

    def _train_export_path(self):
        from robot.policy_io import normalize_policy_base_name, checkpoint_bin_path

        base = normalize_policy_base_name(self.export_policy_var.get())
        return checkpoint_bin_path(base)

    def _infer_policy_bin(self):
        from robot.policy_io import policy_bin_path

        name = self.infer_policy_var.get().strip()
        if not name:
            raise FileNotFoundError("Chọn file policy .bin trong checkpoints/")
        path = policy_bin_path(name)
        if not os.path.isfile(path):
            raise FileNotFoundError("Không tìm thấy policy: %s" % path)
        return path

    def _build_workspace(self):
        self.workspace = ttk.Frame(self.container)
        self.workspace.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.log_frame = ttk.LabelFrame(self.workspace, text="Output", padding=8)
        self.log = scrolledtext.ScrolledText(self.log_frame, height=16, state=tk.DISABLED, font=("Monospace", 10))
        self.log.pack(fill=tk.BOTH, expand=True)

        self.map_frame = ttk.LabelFrame(self.workspace, text="Map", padding=8)
        self.map_view = SimMapCanvas(self.map_frame)
        self.map_view.pack(fill=tk.BOTH, expand=True)

        self.maps_frame = ttk.LabelFrame(self.workspace, text="List map", padding=8)

        self.workspace.columnconfigure(0, weight=3, minsize=360)
        self.workspace.columnconfigure(1, weight=2, minsize=300)
        self.workspace.rowconfigure(0, weight=1)

    def _build_map_list(self):
        frame = self.maps_frame

        self.map_hint = ttk.Label(frame, text="")
        self.map_hint.pack(anchor=tk.W, pady=(0, 4))

        self.train_cfg_frame = ttk.LabelFrame(frame, text="Danh sách map train", padding=6)
        mode_row = ttk.Frame(self.train_cfg_frame)
        mode_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(mode_row, text="Chế độ train:").pack(side=tk.LEFT, padx=(0, 8))
        self.train_mode_group = SegmentGroup(
            mode_row,
            self.train_map_mode,
            [("Random", "random"), ("Lần lượt", "sequential"), ("Đơn map", "single")],
            command=self._on_train_mode_change,
        )
        self.train_mode_group.pack(side=tk.LEFT)

        tree_wrap = ttk.Frame(self.train_cfg_frame)
        tree_wrap.pack(fill=tk.BOTH, expand=True)
        scroll_t = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL)
        self.train_tree = ttk.Treeview(
            tree_wrap,
            columns=("on", "ord", "name", "eps"),
            show="headings",
            height=14,
            yscrollcommand=scroll_t.set,
            selectmode="browse",
        )
        scroll_t.config(command=self.train_tree.yview)
        style_train_treeview(self.train_tree, self.root)
        self.train_tree.heading("ord", text="≡")
        self.train_tree.heading("name", text="File map")
        self.train_tree.heading("eps", text="Episodes")
        self.train_tree.column("ord", width=32, anchor=tk.CENTER, stretch=False)
        self.train_tree.column("name", width=200, anchor=tk.W, stretch=True)
        self.train_tree.column("eps", width=80, anchor=tk.CENTER, stretch=False)
        self.train_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_t.pack(side=tk.RIGHT, fill=tk.Y)
        self.train_tree.bind("<<TreeviewSelect>>", self._on_train_tree_select)
        self.train_tree.bind("<Button-1>", self._on_train_tree_click, add=True)
        self.train_tree.bind("<ButtonRelease-1>", self._on_train_drag_release, add=True)
        self.train_tree.bind("<B1-Motion>", self._on_train_drag_motion, add=True)

        btn_row = ttk.Frame(self.train_cfg_frame)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        box_button(btn_row, text="Tất cả", command=self._train_select_all, role="accent").pack(side=tk.LEFT, padx=(0, 4))
        box_button(btn_row, text="Bỏ chọn", command=self._train_select_none, role="secondary").pack(side=tk.LEFT, padx=4)

        self.infer_list_frame = ttk.LabelFrame(frame, text="Chọn map infer", padding=6)
        list_frame = ttk.Frame(self.infer_list_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.map_list = tk.Listbox(
            list_frame,
            height=14,
            yscrollcommand=scroll.set,
            selectmode=tk.BROWSE,
            relief=tk.GROOVE,
            bd=2,
            highlightthickness=1,
            selectbackground="#89b4fa",
            selectforeground="#11111b",
            font=("", 10),
        )
        scroll.config(command=self.map_list.yview)
        self.map_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.map_list.bind("<<ListboxSelect>>", self._on_map_select)

    def _build_actions(self):
        bar = ttk.LabelFrame(self.container, text="Train / Inference", padding=8)
        bar.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.btn_run = ttk.Button(bar, text="▶ Run", command=self.on_run)
        self.btn_run.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(bar, text="■ Stop", command=self.on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        ttk.Button(bar, text="Refresh map", command=self.refresh_map_view).pack(side=tk.LEFT, padx=(8, 0))
        self.status = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.status).pack(side=tk.LEFT, padx=12)

    def _on_train_mode_change(self):
        mode = self.train_map_mode.get()
        if mode == "random":
            self.spin_ep.configure(state=tk.NORMAL)
        else:
            self.spin_ep.configure(state=tk.DISABLED)

    def _train_row_by_iid(self, iid):
        if not iid:
            return None
        try:
            idx = int(iid)
        except ValueError:
            return None
        if 0 <= idx < len(self._train_rows):
            return self._train_rows[idx]
        return None

    def _refresh_train_tree(self):
        self._cancel_eps_edit()
        self.train_tree.delete(*self.train_tree.get_children())
        for i, row in enumerate(self._train_rows):
            mark = train_map_mark(row["enabled"])
            tags = train_row_tags(row["enabled"], i)
            self.train_tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(mark, i + 1, row["name"], row["episodes"]),
                tags=tags,
            )

    def _cancel_eps_edit(self):
        if self._eps_entry is not None:
            self._eps_entry.destroy()
            self._eps_entry = None
            self._eps_edit_iid = None

    def _start_eps_edit(self, iid):
        self._cancel_eps_edit()
        bbox = self.train_tree.bbox(iid, column="#4")
        if not bbox:
            return
        row = self._train_row_by_iid(iid)
        if not row:
            return
        x, y, w, h = bbox
        self._eps_edit_iid = iid
        self._eps_entry = ttk.Entry(self.train_tree, width=8, justify=tk.CENTER)
        self._eps_entry.insert(0, str(row["episodes"]))
        self._eps_entry.place(x=x, y=y, width=max(w, 64), height=h)
        self._eps_entry.focus_set()
        self._eps_entry.select_range(0, tk.END)
        self._eps_entry.bind("<Return>", self._finish_eps_edit)
        self._eps_entry.bind("<Escape>", lambda _e: self._cancel_eps_edit())
        self._eps_entry.bind("<FocusOut>", lambda _e: self.root.after(80, self._finish_eps_edit_if_blur))

    def _finish_eps_edit_if_blur(self):
        if self._eps_entry is None:
            return
        try:
            if self.root.focus_get() is self._eps_entry:
                return
        except (KeyError, tk.TclError):
            pass
        self._finish_eps_edit()

    def _finish_eps_edit(self, _event=None):
        if self._eps_entry is None or self._eps_edit_iid is None:
            return
        iid = self._eps_edit_iid
        row = self._train_row_by_iid(iid)
        text = self._eps_entry.get().strip()
        self._cancel_eps_edit()
        if not row:
            return
        try:
            n = max(1, int(text))
        except ValueError:
            messagebox.showwarning("Episodes", "Nhập số nguyên dương.")
            self._refresh_train_tree()
            self.train_tree.selection_set(iid)
            return
        row["episodes"] = n
        self._refresh_train_tree()
        self.train_tree.selection_set(iid)

    def _on_train_tree_select(self, _event=None):
        if self._eps_entry is not None:
            return
        if self.view.get() == "map" and not self._running:
            self._preview_map_from_selection()

    def _on_train_tree_click(self, event):
        if self.train_tree.identify_region(event.x, event.y) != "cell":
            return
        col = self.train_tree.identify_column(event.x)
        iid = self.train_tree.identify_row(event.y)
        if not iid:
            return
        if col == "#1":
            self.train_tree.selection_set(iid)
            self._train_toggle_selected()
            return "break"
        if col == "#4":
            self.train_tree.selection_set(iid)
            self.root.after_idle(lambda i=iid: self._start_eps_edit(i))
            return "break"
        if col in ("#2", "#3"):
            self._drag_src_iid = iid
            self.train_tree.selection_set(iid)

    def _on_train_drag_motion(self, event):
        if not self._drag_src_iid:
            return
        target = self.train_tree.identify_row(event.y)
        for iid in self.train_tree.get_children():
            tags = list(self.train_tree.item(iid, "tags"))
            tags = [t for t in tags if t != "drag_over"]
            self.train_tree.item(iid, tags=tags)
        if target and target != self._drag_src_iid:
            tags = list(self.train_tree.item(target, "tags"))
            if "drag_over" not in tags:
                tags.append("drag_over")
            self.train_tree.item(target, tags=tags)

    def _on_train_drag_release(self, event):
        if not self._drag_src_iid:
            return
        src = int(self._drag_src_iid)
        target_iid = self.train_tree.identify_row(event.y)
        self._drag_src_iid = None
        for iid in self.train_tree.get_children():
            tags = [t for t in self.train_tree.item(iid, "tags") if t != "drag_over"]
            self.train_tree.item(iid, tags=tags)
        if not target_iid:
            return
        dst = int(target_iid)
        if src == dst:
            return
        self._train_reorder(src, dst)

    def _train_reorder(self, src_idx, dst_idx):
        rows = self._train_rows
        if src_idx < 0 or src_idx >= len(rows) or dst_idx < 0 or dst_idx >= len(rows):
            return
        item = rows.pop(src_idx)
        rows.insert(dst_idx, item)
        for i, r in enumerate(rows):
            r["order"] = i
        self._refresh_train_tree()
        self.train_tree.selection_set(str(dst_idx))
        self.train_tree.see(str(dst_idx))

    def _sync_train_rows_from_paths(self):
        old = {r["name"]: r for r in self._train_rows}
        rows = []
        for path in self._map_paths:
            name = os.path.basename(path)
            prev = old.get(name, {})
            rows.append(
                {
                    "path": path,
                    "name": name,
                    "enabled": prev.get("enabled", True),
                    "episodes": prev.get("episodes", 1000),
                    "order": prev.get("order", len(rows)),
                }
            )
        rows.sort(key=lambda r: r["order"])
        for i, r in enumerate(rows):
            r["order"] = i
        self._train_rows = rows
        self._refresh_train_tree()

    def _train_toggle_selected(self):
        sel = self.train_tree.selection()
        if not sel:
            return
        row = self._train_row_by_iid(sel[0])
        if row:
            row["enabled"] = not row["enabled"]
            self._refresh_train_tree()
            self.train_tree.selection_set(sel[0])

    def _train_select_all(self):
        for row in self._train_rows:
            row["enabled"] = True
        self._refresh_train_tree()

    def _train_select_none(self):
        for row in self._train_rows:
            row["enabled"] = False
        self._refresh_train_tree()

    def _build_train_run_config(self):
        mode = self.train_map_mode.get()
        if mode == "single":
            sel = self.train_tree.selection()
            if not sel:
                raise ValueError("Chế độ Đơn map — chọn một dòng trong bảng.")
            row = self._train_row_by_iid(sel[0])
            if not row:
                raise ValueError("Map không hợp lệ.")
            sim = build_sim_map_from_file(row["path"])
            n_ep = max(1, int(row["episodes"]))
            return "random", [sim], None, n_ep

        enabled = [r for r in self._train_rows if r["enabled"]]
        if not enabled:
            raise ValueError("Chọn ít nhất một map train (bấm ô [ ]).")
        if mode == "sequential":
            ordered = sorted(enabled, key=lambda r: r["order"])
            plan = []
            sims = []
            for r in ordered:
                sim = build_sim_map_from_file(r["path"])
                plan.append((sim, int(r["episodes"])))
                sims.append(sim)
            total = sum(r["episodes"] for r in ordered)
            return mode, sims, plan, total
        sims = [build_sim_map_from_file(r["path"]) for r in enabled]
        try:
            n_ep = int(self.spin_ep.get())
        except ValueError:
            n_ep = 10000
        return mode, sims, None, n_ep

    def _start_train(self):
        if self._running:
            return
        if not self._map_paths:
            messagebox.showwarning("Train", "Không có map trong map/train/")
            return
        self._cancel_eps_edit()
        try:
            self._build_train_run_config()
            export_path = self._train_export_path()
        except (ValueError, Exception) as exc:
            messagebox.showwarning("Train", str(exc))
            return
        if self.view.get() == "map":
            self._run_train_map(export_path)
        else:
            self._run_train_log(export_path)

    def notify_map_saved(self, kind, path):
        """Gọi từ tab Tạo map sau khi Save JSON."""
        self.root.after(0, lambda: self._handle_map_saved(kind, path))

    def _handle_map_saved(self, kind, path):
        if self._running:
            return
        basename = os.path.basename(path)
        if kind == "train" or (kind == "infer" and self.mode.get() == "infer"):
            self.refresh_maps()
            if kind == "train":
                for i, row in enumerate(self._train_rows):
                    if row["name"] == basename:
                        row["enabled"] = True
                        self._refresh_train_tree()
                        self.train_tree.selection_set(str(i))
                        self.train_tree.see(str(i))
                        break
            elif self._map_paths:
                for i, p in enumerate(self._map_paths):
                    if os.path.basename(p) == basename:
                        self.map_list.selection_clear(0, tk.END)
                        self.map_list.selection_set(i)
                        self.map_list.see(i)
                        break
            if self.view.get() == "map":
                self._preview_map_from_selection()
            self.status.set("Đã refresh — map mới: %s" % basename)

    def _step_delay_ms(self):
        try:
            return max(1, int(self.step_delay.get()))
        except ValueError:
            return 200

    def _on_mode_change(self):
        self.refresh_maps()
        if self.mode.get() == "train":
            self.infer_policy_frame.pack_forget()
            self.ck_frame.pack(fill=tk.X, padx=8, before=self.workspace)
            self.train_cfg_frame.pack(fill=tk.BOTH, expand=True)
            self.infer_list_frame.pack_forget()
            self.refresh_checkpoints()
            self._on_train_mode_change()
        else:
            self.ck_frame.pack_forget()
            self.infer_policy_frame.pack(fill=tk.X, padx=8, before=self.workspace)
            self.train_cfg_frame.pack_forget()
            self.infer_list_frame.pack(fill=tk.BOTH, expand=True)
            self.refresh_infer_policies()
            self.spin_ep.configure(state=tk.DISABLED)
        self._update_view_widgets()

    def _on_view_change(self):
        self._update_view_widgets()

    def _on_map_select(self, _event=None):
        if self.view.get() == "map" and not self._running:
            self._preview_map_from_selection()

    def _preview_map_from_selection(self):
        if self.mode.get() == "train":
            sel = self.train_tree.selection()
            if sel:
                row = self._train_row_by_iid(sel[0])
                if row:
                    for i, path in enumerate(self._map_paths):
                        if path == row["path"]:
                            self._preview_map(i)
                            return
            if self._train_rows:
                for i, path in enumerate(self._map_paths):
                    if path == self._train_rows[0]["path"]:
                        self._preview_map(i)
                        return
            return
        sel = self.map_list.curselection()
        if sel:
            self._preview_map(sel[0])
        elif self._map_paths:
            self._preview_map(0)

    def _preview_map(self, idx):
        if idx < 0 or idx >= len(self._map_paths):
            return
        try:
            path = self._map_paths[idx]
            sim = build_sim_map_from_file(path)
            self.map_view.load_sim_map(sim)
            self.map_view.reset_path()
            name = sim.get("name", os.path.basename(path))
            mode = self.mode.get()
            if mode == "train":
                hint = "%s (%dx%d) — preview | Run để xem train từng bước"
            else:
                hint = "%s (%dx%d) — bấm Run để chạy infer"
            self.map_view.set_status(hint % (name, sim["width"], sim["height"]))
            self.status.set("Map loaded")
            self.root.after_idle(self.map_view.redraw)
        except Exception as exc:
            self.map_view.set_status("Lỗi load map: %s" % exc)

    def _update_view_widgets(self):
        is_map = self.view.get() == "map"
        self.log_frame.grid_remove()
        self.map_frame.grid_remove()
        if is_map:
            self.map_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            self.delay_group.set_enabled(True)
            self._preview_map_from_selection()
        else:
            self.log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
            self.delay_group.set_enabled(False)
        self.maps_frame.grid(row=0, column=1, sticky="nsew")

    def refresh_maps(self):
        kind = "train" if self.mode.get() == "train" else "infer"
        self._map_paths = list_map_files(kind)
        if self.mode.get() == "train":
            self._sync_train_rows_from_paths()
            self.map_hint.config(
                text="[ ] bật/tắt map | kéo ≡/tên đổi thứ tự | bấm Episodes sửa | Đơn map = 1 dòng đang chọn"
            )
            self.spin_ep.configure(state=tk.NORMAL if self.train_map_mode.get() == "random" else tk.DISABLED)
        else:
            self.map_list.delete(0, tk.END)
            for path in self._map_paths:
                self.map_list.insert(tk.END, os.path.basename(path))
            self.map_hint.config(text="Infer: chọn map. Map + Run để xem robot infer từng bước.")
            self.spin_ep.configure(state=tk.DISABLED)
            if self._map_paths:
                self.map_list.selection_set(0)
        if self.view.get() == "map":
            self.root.after_idle(self._preview_map_from_selection)

    def refresh_map_view(self):
        """Đọc lại map từ map/train|infer/ và vẽ lại bản đồ đang chọn."""
        if self._running:
            messagebox.showinfo("Refresh map", "Đang chạy train/infer — bấm Stop hoặc đợi xong.")
            return
        kind = "train" if self.mode.get() == "train" else "infer"
        prev_name = None
        if self.mode.get() == "train":
            sel = self.train_tree.selection()
            if sel:
                row = self._train_row_by_iid(sel[0])
                if row:
                    prev_name = row["name"]
        else:
            prev_sel = self.map_list.curselection()
            if prev_sel and prev_sel[0] < len(self._map_paths):
                prev_name = os.path.basename(self._map_paths[prev_sel[0]])
        self.refresh_maps()
        if prev_name and self._map_paths:
            if self.mode.get() == "train":
                for i, row in enumerate(self._train_rows):
                    if row["name"] == prev_name:
                        self.train_tree.selection_set(str(i))
                        self.train_tree.see(str(i))
                        break
            else:
                for i, path in enumerate(self._map_paths):
                    if os.path.basename(path) == prev_name:
                        self.map_list.selection_clear(0, tk.END)
                        self.map_list.selection_set(i)
                        self.map_list.see(i)
                        break
        n = len(self._map_paths)
        if self.view.get() == "map":
            self._preview_map_from_selection()
            self.status.set("Refresh map — %d file trong map/%s/" % (n, kind))
        else:
            self.status.set("Refresh map — %d file trong map/%s/ (chọn View Map để xem)" % (n, kind))

    def on_run(self):
        if self._running:
            return

        if self.mode.get() == "infer":
            sel = self.map_list.curselection()
            if not self._map_paths:
                messagebox.showwarning("Infer", "Không có map trong map/infer/")
                return
            if not sel:
                messagebox.showwarning("Infer", "Chọn một map infer.")
                return
            try:
                self._infer_policy_bin()
            except FileNotFoundError as exc:
                messagebox.showwarning("Infer", str(exc))
                return
            if self.view.get() == "map":
                self._run_infer_map(sel[0])
            else:
                self._run_infer_log(sel[0])
            return

        self._start_train()

    def _should_stop_train(self):
        return self._stop_requested

    def on_stop(self):
        if not self._running:
            return
        self._stop_requested = True
        if self.mode.get() == "train":
            self._ui_done.set()
            self.status.set("Stopping...")
        else:
            if self._anim_after_id:
                self.root.after_cancel(self._anim_after_id)
                self._anim_after_id = None
            self._running = False
            self.btn_run.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
            self.status.set("Stopped")
            self.map_view.set_status("Đã dừng infer")


    def _begin_train(self):
        self._running = True
        self._stop_requested = False
        self.btn_run.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)

    def _end_train(self, stopped=False, episodes_done=0, export_path=None):
        self._running = False
        self._stop_requested = False
        self.btn_run.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        export_name = os.path.basename(export_path) if export_path else ""
        if stopped:
            self.status.set("Stopped — đã lưu %s (%d episodes)" % (export_name or "policy", episodes_done))
            if self.view.get() == "map":
                self.map_view.set_status(
                    "Đã dừng — lưu %s (%d episodes)" % (export_name or "policy", episodes_done)
                )
        else:
            self.status.set("Done — %s" % (export_name or "policy"))
            if self.view.get() == "map" and self.mode.get() == "train":
                self.map_view.set_status("Train xong — đã lưu %s" % (export_name or "policy"))
        self.refresh_checkpoints()
        self.refresh_infer_policies()
        if export_name:
            self.infer_policy_var.set(export_name)
            self.export_policy_var.set(os.path.splitext(export_name)[0])

    def _ui_sync(self, fn):
        """Chạy fn trên main thread và chờ xong (dùng từ thread train)."""
        if self._stop_requested:
            return
        self._ui_done.clear()

        def wrapper():
            try:
                fn()
            finally:
                self._ui_done.set()

        self.root.after(0, wrapper)
        self._ui_done.wait()

    def _ui_sync_after_delay(self, fn, delay_ms):
        if self._stop_requested:
            return
        self._ui_done.clear()

        def wrapper():
            fn()
            self.root.after(delay_ms, self._ui_done.set)

        self.root.after(0, wrapper)
        self._ui_done.wait()

    def _make_train_callbacks(self, n_episodes):
        def on_episode_start(sim, ep, eps, total):
            if self._stop_requested:
                return

            def show():
                self.map_view.load_sim_map(sim)
                self.map_view.reset_path()
                name = sim.get("name", "?")
                self.map_view.set_status(
                    "Episode %d/%d | map: %s | ε=%.3f" % (ep + 1, total, name, eps)
                )
                self.status.set("Training episode %d/%d" % (ep + 1, total))

            self._ui_sync(show)

        def on_step(entry):
            if self._stop_requested:
                return
            delay = self._step_delay_ms()

            def show():
                self.map_view.show_step(entry)

            self._ui_sync_after_delay(show, delay)

        return on_episode_start, on_step

    def _run_train_log(self, export_path):
        self._begin_train()
        self.status.set("Running...")
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

        try:
            mode, sims, plan, n_ep = self._build_train_run_config()
        except ValueError as exc:
            messagebox.showwarning("Train", str(exc))
            self._end_train(False, 0)
            return

        def work():
            import rl_runner

            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log, self.root)
            try:
                result = rl_runner.run_train(
                    n_episodes=n_ep,
                    should_stop=self._should_stop_train,
                    checkpoint=self._train_checkpoint_spec(),
                    train_map_mode=mode,
                    train_sims=sims,
                    sequential_plan=plan,
                    export_policy_path=export_path,
                )
            except Exception as exc:
                print("ERROR:", exc)
                result = {"stopped": False}
            finally:
                sys.stdout = old_stdout
                stopped = result.get("stopped", False) if isinstance(result, dict) else False
                ep_done = result.get("episodes_done", 0) if isinstance(result, dict) else 0
                out = result.get("export_path", export_path) if isinstance(result, dict) else export_path
                self.root.after(0, lambda s=stopped, e=ep_done, p=out: self._end_train(s, e, p))

        threading.Thread(target=work, daemon=True).start()

    def _run_train_map(self, export_path):
        self._begin_train()
        self.status.set("Training...")
        if self._anim_after_id:
            self.root.after_cancel(self._anim_after_id)
            self._anim_after_id = None

        try:
            mode, sims, plan, n_ep = self._build_train_run_config()
        except ValueError as exc:
            messagebox.showwarning("Train", str(exc))
            self._end_train(False, 0)
            return

        on_episode_start, on_step = self._make_train_callbacks(n_ep)

        def work():
            import rl_runner

            try:
                result = rl_runner.run_train(
                    n_episodes=n_ep,
                    on_episode_start=on_episode_start,
                    on_step=on_step,
                    step_wait=None,
                    should_stop=self._should_stop_train,
                    checkpoint=self._train_checkpoint_spec(),
                    train_map_mode=mode,
                    train_sims=sims,
                    sequential_plan=plan,
                    export_policy_path=export_path,
                )
                stopped = result.get("stopped", False)
                ep_done = result.get("episodes_done", 0)
                out = result.get("export_path", export_path)
                self.root.after(0, lambda s=stopped, e=ep_done, p=out: self._end_train(s, e, p))
            except Exception as exc:
                self.root.after(0, lambda err=exc: self._infer_error(err))

        threading.Thread(target=work, daemon=True).start()

    def _run_infer_log(self, idx):
        map_path = self._map_paths[idx]
        policy_bin = self._infer_policy_bin()
        self._running = True
        self._stop_requested = False
        self.btn_run.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.status.set("Running...")
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

        def work():
            import rl_runner

            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log, self.root)
            try:
                rl_runner.run_infer_episode_for_map(
                    map_path, verbose=True, policy_bin=policy_bin
                )
            except Exception as exc:
                print("ERROR:", exc)
            finally:
                sys.stdout = old_stdout
                self.root.after(0, self._run_done)

        threading.Thread(target=work, daemon=True).start()

    def _run_infer_map(self, idx):
        map_path = self._map_paths[idx]
        policy_bin = self._infer_policy_bin()
        self._running = True
        self._stop_requested = False
        self.btn_run.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.status.set("Computing path...")
        if self._anim_after_id:
            self.root.after_cancel(self._anim_after_id)
            self._anim_after_id = None

        def work():
            import rl_runner

            try:
                sim, outcome = rl_runner.run_infer_episode_for_map(
                    map_path, verbose=False, policy_bin=policy_bin
                )
                self.root.after(0, lambda s=sim, o=outcome: self._start_animation(s, o))
            except Exception as exc:
                self.root.after(0, lambda err=exc: self._infer_error(err))

        threading.Thread(target=work, daemon=True).start()

    def _infer_error(self, exc):
        self._running = False
        self._stop_requested = False
        self.btn_run.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.status.set("Error")
        messagebox.showerror("Error", str(exc))

    def _start_animation(self, sim_map, outcome):
        delay = self._step_delay_ms()

        self.map_view.load_sim_map(sim_map)
        self.map_view.reset_path()
        self.status.set("Playing...")
        log = outcome.get("log") or []
        self._play_steps(log, 0, outcome, delay)

    def _play_steps(self, log, index, outcome, delay):
        if index >= len(log):
            status = outcome.get("status", "?")
            steps = outcome.get("steps", 0)
            if status == "goal":
                msg = "GOAL — %d bước" % steps
            elif status == "collision":
                msg = "COLLISION — dừng ở bước %d" % steps
            else:
                msg = "Kết thúc: %s (%d bước)" % (status, steps)
            self.map_view.set_status(msg)
            self.status.set("Done — " + msg)
            self._running = False
            self.btn_run.configure(state=tk.NORMAL)
            return

        entry = log[index]
        self.map_view.show_step(entry)
        self._anim_after_id = self.root.after(delay, lambda: self._play_steps(log, index + 1, outcome, delay))

    def _run_done(self):
        self._running = False
        self._stop_requested = False
        self.btn_run.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.status.set("Done")

    def run(self):
        if self._standalone:
            self.root.mainloop()


def run_app(parent=None, root=None):
    app = RlApp(parent=parent, root=root)
    if parent is None:
        app.run()
    return app
