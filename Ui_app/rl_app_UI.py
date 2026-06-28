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
        self.widget.insert(tk.END, text)
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
        self.step_delay = tk.IntVar(value=400)
        self.checkpoint_var = tk.StringVar(value="(mới)")
        self.infer_policy_var = tk.StringVar(value="policy.bin")
        self._running = False
        self._stop_requested = False
        self._map_paths = []
        self._train_rows = []
        self._anim_after_id = None
        self._ui_done = threading.Event()
        self.train_map_mode = tk.StringVar(value="random")
        self._train_eps_var = tk.StringVar(value="1000")

        self._build_toolbar()
        self._build_checkpoint_bar()
        self._build_infer_policy_bar()
        self._build_map_list()
        self._build_content()
        self._build_actions()
        self.mode.trace_add("write", lambda *_: self._on_mode_change())
        self.view.trace_add("write", lambda *_: self._on_view_change())
        self._on_mode_change()

    def _build_toolbar(self):
        bar = ttk.Frame(self.container, padding=8)
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="Mode").grid(row=0, column=0, padx=(0, 8))
        ttk.Radiobutton(bar, text="Train", variable=self.mode, value="train").grid(row=0, column=1)
        ttk.Radiobutton(bar, text="Infer", variable=self.mode, value="infer").grid(row=0, column=2, padx=(0, 16))

        ttk.Separator(bar, orient=tk.VERTICAL).grid(row=0, column=3, sticky="ns", padx=8)

        ttk.Label(bar, text="View").grid(row=0, column=4, padx=(0, 4))
        ttk.Radiobutton(bar, text="Log", variable=self.view, value="log").grid(row=0, column=5)
        ttk.Radiobutton(bar, text="Map", variable=self.view, value="map").grid(row=0, column=6, padx=(0, 12))

        ttk.Label(bar, text="Episodes").grid(row=0, column=7, padx=(0, 4))
        self.spin_ep = ttk.Spinbox(bar, from_=100, to=200000, increment=100, width=8)
        self.spin_ep.set(str(self.episodes.get()))
        self.spin_ep.grid(row=0, column=8, padx=(0, 12))

        ttk.Label(bar, text="ms/step").grid(row=0, column=9, padx=(0, 4))
        self.spin_delay = ttk.Spinbox(bar, from_=50, to=3000, increment=50, width=5)
        self.spin_delay.set(str(self.step_delay.get()))
        self.spin_delay.grid(row=0, column=10, padx=(0, 8))

        ttk.Button(bar, text="Refresh maps", command=self.refresh_maps).grid(row=0, column=11)

    def _build_checkpoint_bar(self):
        self.ck_frame = ttk.Frame(self.container, padding=(8, 4))
        self.ck_frame.pack(fill=tk.X)
        ttk.Label(self.ck_frame, text="Checkpoint").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_checkpoint = ttk.Combobox(
            self.ck_frame,
            textvariable=self.checkpoint_var,
            width=28,
            state="readonly",
        )
        self.combo_checkpoint.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(self.ck_frame, text="Refresh Q", command=self.refresh_checkpoints).pack(side=tk.LEFT)
        ttk.Label(
            self.ck_frame,
            text="Train mới hoặc chọn Q_table có sẵn — export ghi policy.bin",
        ).pack(side=tk.LEFT, padx=8)
        self.refresh_checkpoints()

    def _build_infer_policy_bar(self):
        self.infer_policy_frame = ttk.Frame(self.container, padding=(8, 4))
        ttk.Label(self.infer_policy_frame, text="Policy").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_infer_policy = ttk.Combobox(
            self.infer_policy_frame,
            textvariable=self.infer_policy_var,
            width=28,
            state="readonly",
        )
        self.combo_infer_policy.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(self.infer_policy_frame, text="Refresh list", command=self.refresh_infer_policies).pack(
            side=tk.LEFT
        )
        ttk.Label(
            self.infer_policy_frame,
            text="Chọn file Q_table/*.bin để infer",
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
        from robot.policy_io import list_checkpoints

        prev = self.checkpoint_var.get()
        names = list_checkpoints()
        values = ["(mới)"] + names
        self.combo_checkpoint["values"] = values
        if prev in values:
            self.checkpoint_var.set(prev)
        elif "policy" in names:
            self.checkpoint_var.set("policy")
        else:
            self.checkpoint_var.set("(mới)")

    def _train_checkpoint_spec(self):
        val = self.checkpoint_var.get().strip()
        if not val or val == "(mới)":
            return None
        return val

    def _infer_policy_bin(self):
        from robot.policy_io import policy_bin_path

        name = self.infer_policy_var.get().strip()
        if not name:
            raise FileNotFoundError("Chọn file policy .bin trong Q_table/")
        path = policy_bin_path(name)
        if not os.path.isfile(path):
            raise FileNotFoundError("Không tìm thấy policy: %s" % path)
        return path

    def _build_map_list(self):
        self.maps_frame = ttk.LabelFrame(self.container, text="Maps", padding=8)
        self.maps_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 4))
        frame = self.maps_frame

        self.map_hint = ttk.Label(frame, text="")
        self.map_hint.pack(anchor=tk.W, pady=(0, 4))

        self.train_cfg_frame = ttk.Frame(frame)
        mode_row = ttk.Frame(self.train_cfg_frame)
        mode_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(mode_row, text="Train maps:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(
            mode_row, text="Random", variable=self.train_map_mode, value="random", command=self._on_train_mode_change
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            mode_row, text="Lần lượt", variable=self.train_map_mode, value="sequential", command=self._on_train_mode_change
        ).pack(side=tk.LEFT, padx=(0, 12))
        self.train_mode_hint = ttk.Label(mode_row, text="")
        self.train_mode_hint.pack(side=tk.LEFT)

        tree_wrap = ttk.Frame(self.train_cfg_frame)
        tree_wrap.pack(fill=tk.BOTH, expand=True)
        scroll_t = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL)
        self.train_tree = ttk.Treeview(
            tree_wrap,
            columns=("on", "ord", "name", "eps"),
            show="headings",
            height=5,
            yscrollcommand=scroll_t.set,
        )
        scroll_t.config(command=self.train_tree.yview)
        self.train_tree.heading("on", text="✓")
        self.train_tree.heading("ord", text="#")
        self.train_tree.heading("name", text="File")
        self.train_tree.heading("eps", text="Episodes")
        self.train_tree.column("on", width=28, anchor=tk.CENTER)
        self.train_tree.column("ord", width=28, anchor=tk.CENTER)
        self.train_tree.column("name", width=220, anchor=tk.W)
        self.train_tree.column("eps", width=72, anchor=tk.CENTER)
        self.train_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_t.pack(side=tk.RIGHT, fill=tk.Y)
        self.train_tree.bind("<<TreeviewSelect>>", self._on_train_tree_select)
        self.train_tree.bind("<Double-1>", self._on_train_tree_double)

        btn_row = ttk.Frame(self.train_cfg_frame)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btn_row, text="↑", width=3, command=self._train_move_up).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_row, text="↓", width=3, command=self._train_move_down).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_row, text="Bật/tắt", command=self._train_toggle_selected).pack(side=tk.LEFT, padx=(8, 2))
        ttk.Button(btn_row, text="Tất cả", command=self._train_select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Bỏ chọn", command=self._train_select_none).pack(side=tk.LEFT, padx=2)
        ttk.Label(btn_row, text="Episodes map:").pack(side=tk.LEFT, padx=(12, 4))
        self.spin_train_eps = ttk.Spinbox(btn_row, from_=1, to=200000, increment=100, width=8, textvariable=self._train_eps_var)
        self.spin_train_eps.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Áp dụng", command=self._train_apply_eps).pack(side=tk.LEFT, padx=4)

        self.infer_list_frame = ttk.Frame(frame)
        list_frame = ttk.Frame(self.infer_list_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.map_list = tk.Listbox(list_frame, height=5, yscrollcommand=scroll.set, selectmode=tk.BROWSE)
        scroll.config(command=self.map_list.yview)
        self.map_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.map_list.bind("<<ListboxSelect>>", self._on_map_select)

    def _build_content(self):
        self.content = ttk.Frame(self.container)
        self.content.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.log_frame = ttk.LabelFrame(self.content, text="Output", padding=8)
        self.log = scrolledtext.ScrolledText(self.log_frame, height=16, state=tk.DISABLED, font=("Monospace", 10))
        self.log.pack(fill=tk.BOTH, expand=True)

        self.map_frame = ttk.LabelFrame(self.content, text="Map", padding=8)
        self.map_view = SimMapCanvas(self.map_frame)
        self.map_view.pack(fill=tk.BOTH, expand=True)

    def _build_actions(self):
        bar = ttk.Frame(self.container, padding=8)
        bar.pack(fill=tk.X)
        self.btn_run = ttk.Button(bar, text="Run", command=self.on_run)
        self.btn_run.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(bar, text="Stop", command=self.on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        ttk.Button(bar, text="Refresh map", command=self.refresh_map_view).pack(side=tk.LEFT, padx=(8, 0))
        self.status = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.status).pack(side=tk.LEFT, padx=12)

    def _on_train_mode_change(self):
        if self.train_map_mode.get() == "random":
            self.train_mode_hint.config(text="Random — dùng Episodes trên toolbar")
            self.spin_ep.configure(state=tk.NORMAL)
        else:
            self.train_mode_hint.config(text="Lần lượt — tổng episodes = sum cột Episodes")
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
        self.train_tree.delete(*self.train_tree.get_children())
        for i, row in enumerate(self._train_rows):
            mark = "✓" if row["enabled"] else " "
            self.train_tree.insert("", tk.END, iid=str(i), values=(mark, i + 1, row["name"], row["episodes"]))

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

    def _on_train_tree_select(self, _event=None):
        sel = self.train_tree.selection()
        if not sel:
            return
        row = self._train_row_by_iid(sel[0])
        if row:
            self._train_eps_var.set(str(row["episodes"]))
        if self.view.get() == "map" and not self._running:
            self._preview_map_from_selection()

    def _on_train_tree_double(self, event):
        iid = self.train_tree.identify_row(event.y)
        if iid:
            self.train_tree.selection_set(iid)
            self._train_toggle_selected()

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

    def _train_move_up(self):
        sel = self.train_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx <= 0:
            return
        self._train_rows[idx]["order"], self._train_rows[idx - 1]["order"] = (
            self._train_rows[idx - 1]["order"],
            self._train_rows[idx]["order"],
        )
        self._train_rows.sort(key=lambda r: r["order"])
        for i, r in enumerate(self._train_rows):
            r["order"] = i
        self._refresh_train_tree()
        self.train_tree.selection_set(str(idx - 1))

    def _train_move_down(self):
        sel = self.train_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._train_rows) - 1:
            return
        self._train_rows[idx]["order"], self._train_rows[idx + 1]["order"] = (
            self._train_rows[idx + 1]["order"],
            self._train_rows[idx]["order"],
        )
        self._train_rows.sort(key=lambda r: r["order"])
        for i, r in enumerate(self._train_rows):
            r["order"] = i
        self._refresh_train_tree()
        self.train_tree.selection_set(str(idx + 1))

    def _train_apply_eps(self):
        sel = self.train_tree.selection()
        if not sel:
            messagebox.showinfo("Train maps", "Chọn một dòng map trước.")
            return
        try:
            n = max(1, int(self._train_eps_var.get()))
        except ValueError:
            messagebox.showwarning("Train maps", "Episodes phải là số nguyên.")
            return
        row = self._train_row_by_iid(sel[0])
        if row:
            row["episodes"] = n
            self._refresh_train_tree()
            self.train_tree.selection_set(sel[0])

    def _build_train_run_config(self):
        enabled = [r for r in self._train_rows if r["enabled"]]
        if not enabled:
            raise ValueError("Chọn ít nhất một map train (cột ✓).")
        mode = self.train_map_mode.get()
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
            return max(50, int(self.spin_delay.get()))
        except ValueError:
            return self.step_delay.get()

    def _on_mode_change(self):
        self.refresh_maps()
        if self.mode.get() == "train":
            self.ck_frame.pack(fill=tk.X, before=self.maps_frame)
            self.infer_policy_frame.pack_forget()
            self.train_cfg_frame.pack(fill=tk.BOTH, expand=True)
            self.infer_list_frame.pack_forget()
            self.refresh_checkpoints()
            self._on_train_mode_change()
        else:
            self.ck_frame.pack_forget()
            self.infer_policy_frame.pack(fill=tk.X, before=self.maps_frame)
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
        except Exception as exc:
            self.map_view.set_status("Lỗi load map: %s" % exc)

    def _update_view_widgets(self):
        is_map = self.view.get() == "map"
        self.log_frame.pack_forget()
        self.map_frame.pack_forget()
        if is_map:
            self.map_frame.pack(fill=tk.BOTH, expand=True)
            self.spin_delay.configure(state=tk.NORMAL)
            self._preview_map_from_selection()
        else:
            self.log_frame.pack(fill=tk.BOTH, expand=True)
            self.spin_delay.configure(state=tk.DISABLED)

    def refresh_maps(self):
        kind = "train" if self.mode.get() == "train" else "infer"
        self._map_paths = list_map_files(kind)
        if self.mode.get() == "train":
            self._sync_train_rows_from_paths()
            self.map_hint.config(
                text="Chọn map ✓, thứ tự ↑↓, Episodes/map. Random hoặc lần lượt — rồi Run."
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

        if not self._map_paths:
            messagebox.showwarning("Train", "Không có map trong map/train/")
            return
        try:
            self._build_train_run_config()
        except ValueError as exc:
            messagebox.showwarning("Train", str(exc))
            return
        if self.view.get() == "map":
            self._run_train_map()
        else:
            self._run_train_log()

    def _should_stop_train(self):
        return self._stop_requested

    def on_stop(self):
        if not self._running or self.mode.get() != "train":
            return
        self._stop_requested = True
        self._ui_done.set()
        self.status.set("Stopping...")

    def _begin_train(self):
        self._running = True
        self._stop_requested = False
        self.btn_run.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)

    def _end_train(self, stopped=False, episodes_done=0):
        self._running = False
        self._stop_requested = False
        self.btn_run.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        if stopped:
            self.status.set("Stopped — Q_table updated (%d episodes)" % episodes_done)
            if self.view.get() == "map":
                self.map_view.set_status("Đã dừng — Q_table đã lưu (%d episodes)" % episodes_done)
        else:
            self.status.set("Done")
            if self.view.get() == "map" and self.mode.get() == "train":
                self.map_view.set_status("Train xong — policy đã export")
        self.refresh_checkpoints()

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

    def _run_train_log(self):
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
                )
            except Exception as exc:
                print("ERROR:", exc)
                result = {"stopped": False}
            finally:
                sys.stdout = old_stdout
                stopped = result.get("stopped", False) if isinstance(result, dict) else False
                ep_done = result.get("episodes_done", 0) if isinstance(result, dict) else 0
                self.root.after(0, lambda s=stopped, e=ep_done: self._end_train(s, e))

        threading.Thread(target=work, daemon=True).start()

    def _run_train_map(self):
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
                )
                stopped = result.get("stopped", False)
                ep_done = result.get("episodes_done", 0)
                self.root.after(0, lambda s=stopped, e=ep_done: self._end_train(s, e))
            except Exception as exc:
                self.root.after(0, lambda err=exc: self._infer_error(err))

        threading.Thread(target=work, daemon=True).start()

    def _run_infer_log(self, idx):
        map_path = self._map_paths[idx]
        policy_bin = self._infer_policy_bin()
        self._running = True
        self.btn_run.configure(state=tk.DISABLED)
        self.status.set("Running...")
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

        def work():
            import rl_runner

            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log, self.root)
            try:
                print("--- SS26 infer (PC simulation) ---")
                print("file:", map_path)
                print("policy:", policy_bin)
                print("---")
                sim, outcome = rl_runner.run_infer_episode_for_map(
                    map_path, verbose=True, policy_bin=policy_bin
                )
                print("map:", sim.get("name", "?"), "%dx%d" % (sim["width"], sim["height"]))
                if outcome["status"] == "goal":
                    print("=====goal success========")
                else:
                    print("--- kết quả:", outcome["status"], "| steps:", outcome["steps"])
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
        self.btn_run.configure(state=tk.DISABLED)
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
