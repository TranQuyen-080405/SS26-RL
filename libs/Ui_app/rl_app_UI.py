"""
UI chọn Train hoặc Infer — map đọc từ map/train/ và map/infer/.
View: Log text hoặc bản đồ (preview + animation train/infer).
"""

import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SIM = os.path.join(_ROOT, "Simulation")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from map.map_io import (
    build_sim_map_from_file,
    find_oversized_train_maps,
    format_oversized_train_maps_message,
    is_bundled_map_path,
    list_map_files,
    maps_dir_for_kind,
)
from Ui_app.map_view import SimMapCanvas
from Ui_app.ui_scale import configure_window, entry_width, font, init as init_ui_scale, px, text_lines
from Ui_app.ui_widgets import SegmentGroup, box_button, style_train_treeview, train_map_mark, train_row_tags
import train_log


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
    def __init__(self, parent=None, root=None, on_maps_changed=None):
        if parent is None:
            self.root = tk.Tk()
            self.root.title("SS26 RL — Train / Inference")
            init_ui_scale(self.root)
            configure_window(self.root, width=1200, height=720, min_width=720, min_height=560)
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
        self._paused = False
        self._map_paths = []
        self._train_rows = []
        self._infer_rows = []
        self._anim_after_id = None
        self._current_sync_evt = None
        self._sync_after_id = None
        self._sync_after_evt = None
        self._locked_view = None
        self._locked_mode = None
        self.train_map_mode = tk.StringVar(value="random")
        self.infer_map_mode = tk.StringVar(value="single")
        self._last_train_mode = "random"
        self._episodes_by_mode = {"random": self.episodes.get()}
        self._drag_src_iid = None
        self._eps_entry = None
        self._eps_edit_iid = None
        self._infer_seq_ctx = None
        self._start_queue_processing()
        self.learn_lab_app = None
        self._on_maps_changed = on_maps_changed

        self._build_toolbar()
        self._build_checkpoint_bar()
        self._build_infer_policy_bar()
        self._build_actions()
        self._build_workspace()
        self._build_map_list()
        self.mode.trace_add("write", lambda *_: self._on_mode_change())
        self.view.trace_add("write", lambda *_: self._on_view_change())
        self._on_mode_change()
        self._sync_formula_combo()

    def _build_toolbar(self):
        bar = ttk.LabelFrame(self.container, text="Bảng điều khiển chung", padding=px(8))
        bar.pack(fill=tk.X, padx=px(8), pady=(px(8), px(4)))

        ttk.Label(bar, text="Mode").grid(row=0, column=0, padx=(0, 8), sticky=tk.W)
        self.mode_group = SegmentGroup(
            bar,
            self.mode,
            [("Train", "train"), ("Inference", "infer")],
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
        self.spin_ep = ttk.Spinbox(bar, from_=100, to=200000, increment=100, width=entry_width(8))
        self.spin_ep.set(str(self.episodes.get()))
        self.spin_ep.grid(row=0, column=8, padx=(0, 12))
        self.spin_ep.bind("<FocusOut>", lambda _e: self._on_random_episodes_changed())
        self.spin_ep.bind("<Return>", lambda _e: self._on_random_episodes_changed())

        ttk.Label(bar, text="Tốc độ").grid(row=0, column=9, padx=(0, 4))
        self.delay_group = SegmentGroup(
            bar,
            self.step_delay,
            [("Nhanh", "1"), ("Chậm", "200")],
        )
        self.delay_group.grid(row=0, column=10, padx=(0, 8))

        ttk.Label(bar, text="Reward").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        self.formula_var = tk.StringVar(value="")
        self.combo_formula = ttk.Combobox(
            bar,
            textvariable=self.formula_var,
            state="readonly",
            width=entry_width(24),
            postcommand=self.refresh_formula_list,
        )
        self.combo_formula.grid(row=1, column=1, columnspan=4, sticky=tk.W, pady=(6, 0), padx=(0, 8))
        self.combo_formula.bind("<<ComboboxSelected>>", self._on_formula_selected)

    def _build_checkpoint_bar(self):
        self.ck_frame = ttk.LabelFrame(self.container, text="Nạp Policy", padding=(8, 6))
        row1 = ttk.Frame(self.ck_frame)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text="Nạp từ").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_checkpoint = ttk.Combobox(
            row1,
            textvariable=self.checkpoint_var,
            width=entry_width(22),
            state="readonly",
        )
        self.combo_checkpoint.pack(side=tk.LEFT, padx=(0, 8))
        self.combo_checkpoint.bind("<<ComboboxSelected>>", self._on_checkpoint_selected)
        box_button(row1, text="Refresh list", command=self.refresh_checkpoints, role="secondary").pack(
            side=tk.LEFT, padx=(0, 4)
        )
        box_button(row1, text="Delete policy", command=self._delete_selected_train_policy, role="secondary").pack(
            side=tk.LEFT, padx=(0, 4)
        )
        box_button(row1, text="Xuất policy ra CSV", command=self._export_policy_to_csv, role="secondary").pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Label(row1, text="Khởi tạo Q_table:").pack(side=tk.LEFT, padx=(8, 4))
        box_button(
            row1,
            text="Ưu tiên thẳng",
            command=lambda: self._create_init_policy("forward"),
            role="secondary",
        ).pack(side=tk.LEFT, padx=(0, 4))
        box_button(
            row1,
            text="Ưu tiên trái",
            command=lambda: self._create_init_policy("left"),
            role="secondary",
        ).pack(side=tk.LEFT, padx=(0, 4))
        box_button(
            row1,
            text="Ưu tiên phải",
            command=lambda: self._create_init_policy("right"),
            role="secondary",
        ).pack(side=tk.LEFT, padx=(0, 4))
        box_button(
            row1,
            text="Ngẫu nhiên",
            command=lambda: self._create_init_policy("random"),
            role="secondary",
        ).pack(side=tk.LEFT, padx=(0, 8))

        row2 = ttk.Frame(self.ck_frame)
        row2.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row2, text="Đặt tên").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_export_policy = ttk.Combobox(
            row2,
            textvariable=self.export_policy_var,
            width=entry_width(22),
        )
        self.combo_export_policy.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(row2, text=".bin").pack(side=tk.LEFT, padx=(0, 8))
        # ttk.Label(
        #     row2,
        #     text="Train mới → đặt tên file; train tiếp → có thể giữ hoặc đổi tên",
        # ).pack(side=tk.LEFT, padx=8)
        self.refresh_checkpoints()

    def _build_infer_policy_bar(self):
        self.infer_policy_frame = ttk.LabelFrame(self.container, text="Policy inference", padding=(8, 6))
        ttk.Label(self.infer_policy_frame, text="Policy").pack(side=tk.LEFT, padx=(0, 4))
        self.combo_infer_policy = ttk.Combobox(
            self.infer_policy_frame,
            textvariable=self.infer_policy_var,
            width=entry_width(28),
            state="readonly",
        )
        self.combo_infer_policy.pack(side=tk.LEFT, padx=(0, 8))
        box_button(
            self.infer_policy_frame, text="Làm mới", command=self.refresh_infer_policies, role="secondary"
        ).pack(side=tk.LEFT, padx=(0, 4))
        box_button(
            self.infer_policy_frame, text="Xóa policy", command=self._delete_selected_policy, role="secondary"
        ).pack(side=tk.LEFT, padx=(0, 4))
        box_button(
            self.infer_policy_frame, text="Xuất file CSV", command=self._export_policy_to_csv, role="secondary"
        ).pack(side=tk.LEFT, padx=(0, 4))
        box_button(
            self.infer_policy_frame, text="Xuất log", command=self._export_infer_log, role="secondary"
        ).pack(side=tk.LEFT, padx=(0, 4))
        self.refresh_infer_policies()

    def _latent_map_dir(self):
        return os.path.join(_ROOT, "latent_map")

    def _list_latent_map_paths(self):
        folder = self._latent_map_dir()
        if not os.path.isdir(folder):
            return []
        paths = []
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(".json"):
                paths.append(os.path.join(folder, name))
        return paths

    def _export_infer_log(self):
        if self._is_busy():
            messagebox.showinfo("Xuất log", "Đang chạy train/inference — vui lòng bấm Stop hoặc đợi chạy xong.")
            return
        try:
            policy_bin = self._infer_policy_bin()
        except FileNotFoundError as exc:
            messagebox.showwarning("Xuất log", str(exc))
            return

        map_paths = self._list_latent_map_paths()
        if not map_paths:
            messagebox.showwarning("Xuất log", "Không có map .json trong thư mục libs/latent_map/.")
            return

        policy_name = os.path.basename(policy_bin)
        default_name = "log_%s.log" % os.path.splitext(policy_name)[0]
        log_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Xuất log infer (actions)",
            defaultextension=".log",
            initialfile=default_name,
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        if not log_path:
            return

        self._begin_run()
        self.status.set("Đang xuất log infer...")

        def finish(stopped=False, error=None):
            self._end_run()
            if error is not None:
                self.status.set("Lỗi xuất log")
                messagebox.showerror("Xuất log", "Không thể xuất log:\n%s" % error)
            elif stopped:
                self.status.set("Đã dừng xuất log")
                messagebox.showinfo("Xuất log", "Đã dừng. File có thể chưa đầy đủ:\n%s" % log_path)
            else:
                self.status.set("Đã xuất log")
                messagebox.showinfo("Xuất log", "Đã xuất file log:\n%s" % log_path)

        def work():
            import rl_runner

            chunks = [train_log.format_export_log_header(policy_name, len(map_paths))]
            try:
                for map_path in map_paths:
                    if self._stop_requested:
                        chunks.append("[Stopped]\n")
                        self._ui_async(lambda: finish(stopped=True))
                        return
                    sim, outcome = rl_runner.run_infer_episode_for_map(
                        map_path,
                        verbose=False,
                        policy_bin=policy_bin,
                        should_stop=lambda: self._stop_requested,
                    )
                    map_label = os.path.splitext(os.path.basename(map_path))[0]
                    chunks.append(
                        train_log.format_episode_actions_log(
                            map_label, sim, outcome, include_reward=False, include_end=True
                        )
                    )
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("".join(chunks))
                self._ui_async(lambda: finish(stopped=False))
            except Exception as exc:
                self._ui_async(lambda err=exc: finish(error=err))

        threading.Thread(target=work, daemon=True).start()

    def _export_policy_to_csv(self):
        if self._is_busy():
            messagebox.showinfo("Xuất policy", "Đang chạy train/inference — vui lòng bấm Stop hoặc đợi chạy xong.")
            return

        if self.mode.get() == "infer":
            name = self.infer_policy_var.get().strip()
        else:
            name = self.checkpoint_var.get().strip()
            if not name or name == "(mới)":
                name = self.export_policy_var.get().strip()
        if not name:
            messagebox.showwarning("Xuất policy", "Chưa chọn policy để xuất.")
            return

        from robot.policy_io import load_policy_bin, policy_bin_path, export_policy_csv

        bin_path = policy_bin_path(name)
        if not os.path.isfile(bin_path):
            messagebox.showerror("Xuất policy", "Không tìm thấy policy: %s" % bin_path)
            return

        base_name = os.path.splitext(os.path.basename(bin_path))[0]
        csv_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Xuất policy dùng để nộp Kaggle",
            defaultextension=".csv",
            initialfile=base_name + ".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not csv_path:
            return
        try:
            export_policy_csv(load_policy_bin(bin_path), csv_path)
            messagebox.showinfo("Xuất policy", "Đã xuất file CSV:\n%s" % csv_path)
        except Exception as exc:
            messagebox.showerror("Xuất policy", "Không thể xuất CSV:\n%s" % exc)

    def _delete_selected_policy(self):
        if self._is_busy():
            messagebox.showinfo("Xóa policy", "Đang chạy train/inference — vui lòng bấm Stop hoặc đợi chạy xong.")
            return
        name = self.infer_policy_var.get().strip()
        if not name:
            messagebox.showinfo("Xóa policy", "Chưa chọn file policy nào để xóa.")
            return
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa file policy '{name}' không?",
            icon="warning"
        )
        if not confirm:
            return
        from robot.policy_io import is_bundled_policy_path, policy_bin_path
        path = policy_bin_path(name)
        if is_bundled_policy_path(path):
            messagebox.showinfo(
                "Xóa policy",
                "Policy mặc định nằm bên trong file .exe nên không thể xóa từ danh sách."
            )
            return
        try:
            if os.path.exists(path):
                os.remove(path)
                self.refresh_infer_policies()
                self.refresh_checkpoints()
            else:
                messagebox.showerror("Lỗi", f"Không tìm thấy file policy '{name}' để xóa.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi xóa file: {str(e)}")

    def _delete_selected_train_policy(self):
        if self._is_busy():
            messagebox.showinfo("Xóa policy", "Đang chạy train/inference — vui lòng bấm Stop hoặc đợi chạy xong.")
            return
        name = self.checkpoint_var.get().strip()
        if not name or name == "(mới)":
            messagebox.showinfo("Xóa policy", "Chưa chọn file policy hợp lệ để xóa.")
            return
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa file policy '{name}' không?",
            icon="warning"
        )
        if not confirm:
            return
        from robot.policy_io import is_bundled_policy_path, policy_bin_path
        path = policy_bin_path(name)
        if is_bundled_policy_path(path):
            messagebox.showinfo(
                "Xóa policy",
                "Policy mặc định nằm bên trong file .exe nên không thể xóa từ danh sách."
            )
            return
        try:
            if os.path.exists(path):
                os.remove(path)
                self.refresh_checkpoints()
                self.refresh_infer_policies()
            else:
                messagebox.showerror("Lỗi", f"Không tìm thấy file policy '{name}' để xóa.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi xóa file: {str(e)}")


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

    def _create_init_policy(self, mode):
        if self._is_busy():
            messagebox.showinfo("Khởi tạo policy", "Đang chạy train/inference — vui lòng bấm Stop hoặc đợi chạy xong.")
            return
        try:
            from robot.policy_io import (
                normalize_policy_base_name,
                checkpoint_bin_path,
                export_policy,
                biased_q_table,
                random_q_table,
            )

            base = normalize_policy_base_name(self.export_policy_var.get())
            path = checkpoint_bin_path(base)
            if mode == "forward":
                q_table = biased_q_table("forward", preferred_value=0.5, other_value=0.0)
                label = "forward"
            elif mode == "left":
                q_table = biased_q_table("rotate left", preferred_value=0.5, other_value=0.0)
                label = "rotate left"
            elif mode == "right":
                q_table = biased_q_table("rotate right", preferred_value=0.5, other_value=0.0)
                label = "rotate right"
            else:
                q_table = random_q_table()
                label = "random"
            export_policy(q_table, path)
            self.refresh_checkpoints()
            self.refresh_infer_policies()
            self.checkpoint_var.set(base)
            self.export_policy_var.set(base)
            self.infer_policy_var.set(base + ".bin")
            self.status.set("Khởi tạo policy '%s' (%s)" % (base, label))
            messagebox.showinfo("Khởi tạo policy", "Đã tạo policy khởi tạo:\n%s" % os.path.basename(path))
        except Exception as exc:
            messagebox.showerror("Khởi tạo policy", str(exc))

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
        self.workspace.pack(fill=tk.BOTH, expand=True, padx=px(8), pady=px(4))

        self._side_col_minsize = px(240)
        self._log_col_minsize = px(220)
        self._map_col_minsize = px(180)

        try:
            pane_bg = ttk.Style().lookup("TFrame", "background")
        except tk.TclError:
            pane_bg = "#f0f0f0"

        self._paned = tk.PanedWindow(
            self.workspace,
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

        self.log_frame = ttk.LabelFrame(self._paned, text="Log", padding=px(8))
        self.log = scrolledtext.ScrolledText(
            self.log_frame,
            height=text_lines(16),
            state=tk.DISABLED,
            font=font(9, family="Monospace"),
            wrap=tk.NONE,
        )
        self.log.pack(fill=tk.BOTH, expand=True)

        self.map_frame = ttk.LabelFrame(self._paned, text="Map", padding=px(8))
        self.map_view = SimMapCanvas(self.map_frame)
        self.map_view.pack(fill=tk.BOTH, expand=True)

        self.maps_frame = ttk.LabelFrame(self._paned, text="List map", padding=px(8))
        self.maps_frame.columnconfigure(0, weight=1)
        self.maps_frame.rowconfigure(0, weight=1)

    def _on_paned_resize(self, _event=None):
        if self.view.get() != "map":
            return
        try:
            self.root.after_idle(self.map_view.redraw)
        except Exception:
            pass

    def _apply_pane_minsizes(self):
        try:
            self._paned.paneconfigure(self.log_frame, minsize=self._log_col_minsize)
            self._paned.paneconfigure(self.maps_frame, minsize=self._side_col_minsize)
            if self.view.get() == "map":
                self._paned.paneconfigure(self.map_frame, minsize=self._map_col_minsize)
        except tk.TclError:
            pass

    def _rebuild_paned_panes(self):
        """Sắp xếp lại pane Log | Map | List map — Map ẩn khi View = Log."""
        for child in (self.log_frame, self.map_frame, self.maps_frame):
            try:
                self._paned.forget(child)
            except tk.TclError:
                pass

        is_map = self.view.get() == "map"
        stretch = "always"
        self._paned.add(self.log_frame, minsize=self._log_col_minsize, stretch=stretch)
        if is_map:
            self._paned.add(self.map_frame, minsize=self._map_col_minsize, stretch=stretch)
        self._paned.add(self.maps_frame, minsize=self._side_col_minsize, stretch=stretch)
        self._apply_pane_minsizes()

        if is_map:
            self.delay_group.set_enabled(True)
            self._preview_map_from_selection()
        else:
            self.delay_group.set_enabled(False)

    def _build_map_list(self):
        frame = self.maps_frame

        self.map_hint = ttk.Label(frame, text="")

        self.train_cfg_frame = ttk.LabelFrame(frame, text="Danh sách map train", padding=6)
        self.train_cfg_frame.columnconfigure(0, weight=1)
        self.train_cfg_frame.rowconfigure(1, weight=1, minsize=px(72))
        self.train_cfg_frame.rowconfigure(2, weight=0, minsize=px(48))

        mode_row = ttk.Frame(self.train_cfg_frame)
        mode_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(mode_row, text="Chế độ train:").pack(side=tk.LEFT, padx=(0, 8))
        self.train_mode_group = SegmentGroup(
            mode_row,
            self.train_map_mode,
            [("Random", "random"), ("Sequence", "sequential"), ("Single", "single"), ("Curriculum", "curriculum")],
            command=self._on_train_mode_change,
        )
        self.train_mode_group.pack(side=tk.LEFT)
        self.curriculum_cfg_frame = ttk.Frame(mode_row)
        self.curriculum_cfg_frame.pack_forget()

        tree_wrap = ttk.Frame(self.train_cfg_frame)
        tree_wrap.grid(row=1, column=0, sticky="nsew")
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)
        scroll_t = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(tree_wrap, orient=tk.HORIZONTAL)
        self.train_tree = ttk.Treeview(
            tree_wrap,
            columns=("on", "ord", "name", "eps"),
            show="headings",
            height=text_lines(8),
            yscrollcommand=scroll_t.set,
            xscrollcommand=scroll_x.set,
            selectmode="browse",
        )
        scroll_t.config(command=self.train_tree.yview)
        scroll_x.config(command=self.train_tree.xview)
        style_train_treeview(self.train_tree, self.root)
        self.train_tree.heading("ord", text="≡")
        self.train_tree.heading("name", text="File map")
        self.train_tree.heading("eps", text="Episodes")
        self.train_tree.column("on", width=px(34), anchor=tk.CENTER, stretch=False, minwidth=px(30))
        self.train_tree.column("ord", width=px(32), anchor=tk.CENTER, stretch=False, minwidth=px(28))
        self.train_tree.column("name", width=px(160), anchor=tk.W, stretch=True, minwidth=px(72))
        self.train_tree.column("eps", width=px(72), anchor=tk.CENTER, stretch=False, minwidth=px(56))
        self.train_tree.grid(row=0, column=0, sticky="nsew")
        scroll_t.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.train_tree.bind("<<TreeviewSelect>>", self._on_train_tree_select)
        self.train_tree.bind("<Button-1>", self._on_train_tree_click, add=True)
        self.train_tree.bind("<ButtonRelease-1>", self._on_train_drag_release, add=True)
        self.train_tree.bind("<B1-Motion>", self._on_train_drag_motion, add=True)

        btn_row = tk.Frame(self.train_cfg_frame, height=px(44))
        btn_row.grid(row=2, column=0, sticky="ew", pady=(px(6), 0))
        btn_row.grid_propagate(False)
        self.btn_train_select_all = box_button(btn_row, text="Chọn tất cả", command=self._train_select_all, role="accent")
        self.btn_train_select_all.pack(side=tk.LEFT, padx=(0, 4), pady=4)
        self.btn_train_select_none = box_button(btn_row, text="Bỏ chọn tất cả", command=self._train_select_none, role="secondary")
        self.btn_train_select_none.pack(side=tk.LEFT, padx=4, pady=4)

        self.infer_list_frame = ttk.LabelFrame(frame, text="Chọn map inference", padding=6)
        infer_mode_row = ttk.Frame(self.infer_list_frame)
        infer_mode_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(infer_mode_row, text="Chế độ infer:").pack(side=tk.LEFT, padx=(0, 8))
        self.infer_mode_group = SegmentGroup(
            infer_mode_row,
            self.infer_map_mode,
            [("Single", "single"), ("Sequence", "sequential")],
            command=self._on_infer_mode_change,
            uniform_width=True,
        )
        self.infer_mode_group.pack(side=tk.LEFT)

        list_frame = ttk.Frame(self.infer_list_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        self.infer_tree = ttk.Treeview(
            list_frame,
            columns=("on", "ord", "name"),
            show="headings",
            height=text_lines(8),
            yscrollcommand=scroll.set,
            xscrollcommand=scroll_x.set,
            selectmode="browse",
        )
        scroll.config(command=self.infer_tree.yview)
        scroll_x.config(command=self.infer_tree.xview)
        style_train_treeview(self.infer_tree, self.root)
        self.infer_tree.heading("on", text="")
        self.infer_tree.heading("ord", text="≡")
        self.infer_tree.heading("name", text="File map")
        self.infer_tree.column("on", width=px(34), anchor=tk.CENTER, stretch=False, minwidth=px(30))
        self.infer_tree.column("ord", width=px(32), anchor=tk.CENTER, stretch=False, minwidth=px(28))
        self.infer_tree.column("name", width=px(160), anchor=tk.W, stretch=True, minwidth=px(72))
        self.infer_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.infer_tree.bind("<<TreeviewSelect>>", self._on_infer_tree_select)
        self.infer_tree.bind("<Button-1>", self._on_infer_tree_click, add=True)
        self.infer_tree.bind("<ButtonRelease-1>", self._on_infer_drag_release, add=True)
        self.infer_tree.bind("<B1-Motion>", self._on_infer_drag_motion, add=True)
        self.btn_row_infer = tk.Frame(self.infer_list_frame, height=px(44))
        self.btn_row_infer.pack(fill=tk.X, pady=(px(4), 0))
        self.btn_row_infer.pack_propagate(False)
        self.btn_infer_select_all = box_button(
            self.btn_row_infer, text="Chọn tất cả", command=self._infer_select_all, role="accent"
        )
        self.btn_infer_select_none = box_button(
            self.btn_row_infer, text="Bỏ chọn tất cả", command=self._infer_select_none, role="secondary"
        )
        self.btn_infer_delete_map = box_button(
            self.btn_row_infer, text="Xóa map", command=self._delete_selected_infer_map, role="secondary"
        )
        self._repack_infer_buttons()

        self._rebuild_paned_panes()

    def _build_actions(self):
        bar = ttk.LabelFrame(self.container, text="Train / Inference", padding=px(8))
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=px(8), pady=(px(4), px(8)))
        self.btn_run = ttk.Button(bar, text="▶ Run", command=self.on_run)
        self.btn_run.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_pause = ttk.Button(bar, text="⏸ Pause", command=self.on_pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(bar, text="■ Stop", command=self.on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        self.status = tk.StringVar(value="Ready")

    def _row_episodes(self, row, mode=None):
        mode = mode or self.train_map_mode.get()
        store = row.get("episodes_by_mode")
        if store is None:
            return max(1, int(row.get("episodes", 1000)))
        if mode not in store:
            store[mode] = 1000
        return max(1, int(store[mode]))

    def _set_row_episodes(self, row, n, mode=None):
        mode = mode or self.train_map_mode.get()
        if mode not in ("sequential", "single"):
            return
        store = row.setdefault("episodes_by_mode", {"sequential": 1000, "single": 1000})
        store[mode] = max(1, int(n))

    def _row_curriculum_goal(self, row):
        return max(1, int(row.get("curriculum_goal_hits", 10)))

    def _set_row_curriculum_goal(self, row, n):
        row["curriculum_goal_hits"] = max(1, int(n))

    def _coerce_curriculum_goal(self, raw):
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 10

    def _save_mode_episode_settings(self, mode):
        if mode == "random":
            try:
                self._episodes_by_mode["random"] = max(1, int(self.spin_ep.get()))
            except ValueError:
                pass
        elif mode == "curriculum":
            pass

    def _restore_mode_episode_settings(self, mode=None):
        mode = mode or self.train_map_mode.get()
        if mode == "random":
            self.spin_ep.configure(state=tk.NORMAL)
            self.spin_ep.set(str(self._episodes_by_mode.get("random", 10000)))
        elif mode == "curriculum":
            self._update_train_episodes_total()
        else:
            self._update_train_episodes_total()

    def _on_random_episodes_changed(self):
        if self.train_map_mode.get() == "random":
            self._save_mode_episode_settings("random")

    def _on_train_mode_change(self):
        prev = self._last_train_mode
        mode = self.train_map_mode.get()
        if prev != mode:
            self._save_mode_episode_settings(prev)
        if mode == "single":
            enabled = [r for r in self._train_rows if r["enabled"]]
            if len(enabled) > 1:
                keep = enabled[0]
                for r in self._train_rows:
                    r["enabled"] = r is keep
            elif len(enabled) == 0 and self._train_rows:
                sel = self.train_tree.selection()
                pick = self._train_row_by_iid(sel[0]) if sel else self._train_rows[0]
                if pick:
                    for r in self._train_rows:
                        r["enabled"] = r is pick
        self._apply_train_mode_ui()
        self._restore_mode_episode_settings(mode)
        self._refresh_train_tree()
        self._last_train_mode = mode

    def _train_tree_display_columns(self):
        if self.train_map_mode.get() == "random":
            return ("on", "ord", "name")
        return ("on", "ord", "eps", "name")

    def _train_eps_column_index(self):
        cols = self._train_tree_display_columns()
        if "eps" not in cols:
            return None
        return "#%d" % (cols.index("eps") + 1)

    def _train_drag_column_indices(self):
        cols = self._train_tree_display_columns()
        out = set()
        for key in ("ord", "name"):
            if key in cols:
                out.add("#%d" % (cols.index(key) + 1))
        return out

    def _apply_train_mode_ui(self):
        mode = self.train_map_mode.get()
        self.train_tree.configure(displaycolumns=self._train_tree_display_columns())
        self.train_tree.column("on", width=px(34), anchor=tk.CENTER, stretch=False, minwidth=px(30))
        self.train_tree.column("ord", width=px(32), anchor=tk.CENTER, stretch=False, minwidth=px(28))
        self.train_tree.column("name", anchor=tk.W, stretch=True, minwidth=px(72))
        if mode != "random":
            self.train_tree.heading("eps", text="Goal qua map" if mode == "curriculum" else "Episodes")
            self.train_tree.column(
                "eps",
                width=px(72),
                anchor=tk.CENTER,
                stretch=False,
                minwidth=px(56),
            )
        if mode == "single":
            self.btn_train_select_all.pack_forget()
            self.btn_train_select_none.pack_forget()
        else:
            self.btn_train_select_all.pack(side=tk.LEFT, padx=(0, 4), pady=4)
            self.btn_train_select_none.pack(side=tk.LEFT, padx=4, pady=4)
        self.curriculum_cfg_frame.pack_forget()

    def _train_enabled_rows(self):
        return [r for r in self._train_rows if r["enabled"]]

    def _update_train_episodes_total(self):
        mode = self.train_map_mode.get()
        if mode == "random":
            return
        enabled = self._train_enabled_rows()
        if mode == "curriculum":
            total_target = sum(self._row_curriculum_goal(r) for r in enabled)
            self.spin_ep.configure(state=tk.DISABLED)
            self.spin_ep.set(str(max(1, total_target) if total_target else 1))
            return
        total = sum(self._row_episodes(r) for r in enabled)
        self.spin_ep.configure(state=tk.DISABLED)
        self.spin_ep.set(str(max(1, total) if total else 1))

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
        mode = self.train_map_mode.get()
        for i, row in enumerate(self._train_rows):
            mark = train_map_mark(row["enabled"])
            tags = train_row_tags(row["enabled"], i)
            eps_val = self._row_curriculum_goal(row) if mode == "curriculum" else self._row_episodes(row)
            self.train_tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(mark, i + 1, row["name"], eps_val),
                tags=tags,
            )
        self._update_train_episodes_total()

    def _cancel_eps_edit(self):
        if self._eps_entry is not None:
            self._eps_entry.destroy()
            self._eps_entry = None
            self._eps_edit_iid = None

    def _start_eps_edit(self, iid):
        self._cancel_eps_edit()
        bbox = self.train_tree.bbox(iid, column="eps")
        if not bbox:
            return
        row = self._train_row_by_iid(iid)
        if not row:
            return
        x, y, w, h = bbox
        self._eps_edit_iid = iid
        self._eps_entry = ttk.Entry(self.train_tree, width=8, justify=tk.CENTER)
        if self.train_map_mode.get() == "curriculum":
            seed = self._row_curriculum_goal(row)
        else:
            seed = self._row_episodes(row)
        self._eps_entry.insert(0, str(seed))
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
        if self.train_map_mode.get() == "curriculum":
            self._set_row_curriculum_goal(row, n)
        else:
            self._set_row_episodes(row, n)
        self._refresh_train_tree()
        self.train_tree.selection_set(iid)
        self._update_train_episodes_total()

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
        eps_col = self._train_eps_column_index()
        if eps_col and col == eps_col and self.train_map_mode.get() != "random":
            self.train_tree.selection_set(iid)
            self.root.after_idle(lambda i=iid: self._start_eps_edit(i))
            return "break"
        if col in self._train_drag_column_indices():
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
            name = os.path.splitext(os.path.basename(path))[0]
            prev = old.get(name, {})
            prev_eps = prev.get("episodes_by_mode")
            if prev_eps is None:
                legacy = prev.get("episodes", 1000)
                prev_eps = {"sequential": legacy, "single": legacy}
            rows.append(
                {
                    "path": path,
                    "name": name,
                    "enabled": prev.get("enabled", True),
                    "episodes_by_mode": dict(prev_eps),
                    "curriculum_goal_hits": self._coerce_curriculum_goal(prev.get("curriculum_goal_hits", 10)),
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
        if not row:
            return
        if self.train_map_mode.get() == "single":
            if row["enabled"]:
                return
            for r in self._train_rows:
                r["enabled"] = False
            row["enabled"] = True
        else:
            row["enabled"] = not row["enabled"]
        self._refresh_train_tree()
        self.train_tree.selection_set(sel[0])
        self._update_train_episodes_total()

    def _train_select_all(self):
        if self.train_map_mode.get() == "single":
            return
        for row in self._train_rows:
            row["enabled"] = True
        self._refresh_train_tree()
        self._update_train_episodes_total()

    def _train_select_none(self):
        if self.train_map_mode.get() == "single":
            return
        for row in self._train_rows:
            row["enabled"] = False
        self._refresh_train_tree()
        self._update_train_episodes_total()

    def _infer_row_by_iid(self, iid):
        if not iid:
            return None
        try:
            idx = int(iid)
        except ValueError:
            return None
        if 0 <= idx < len(self._infer_rows):
            return self._infer_rows[idx]
        return None

    def _refresh_infer_tree(self):
        self.infer_tree.delete(*self.infer_tree.get_children())
        for i, row in enumerate(self._infer_rows):
            mark = train_map_mark(row["enabled"])
            tags = train_row_tags(row["enabled"], i)
            self.infer_tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(mark, i + 1, row["name"]),
                tags=tags,
            )

    def _sync_infer_rows_from_paths(self):
        old = {r["name"]: r for r in self._infer_rows}
        rows = []
        for path in self._map_paths:
            name = os.path.splitext(os.path.basename(path))[0]
            prev = old.get(name, {})
            rows.append(
                {
                    "path": path,
                    "name": name,
                    "enabled": prev.get("enabled", True),
                    "order": prev.get("order", len(rows)),
                }
            )
        rows.sort(key=lambda r: r["order"])
        for i, r in enumerate(rows):
            r["order"] = i
        self._infer_rows = rows
        self._refresh_infer_tree()
        self._on_infer_mode_change()

    def _infer_toggle_selected(self):
        sel = self.infer_tree.selection()
        if not sel:
            return
        row = self._infer_row_by_iid(sel[0])
        if not row:
            return
        if self.infer_map_mode.get() == "single":
            if row["enabled"]:
                return
            for r in self._infer_rows:
                r["enabled"] = False
            row["enabled"] = True
        else:
            row["enabled"] = not row["enabled"]
        self._refresh_infer_tree()
        self.infer_tree.selection_set(sel[0])

    def _infer_select_all(self):
        if self.infer_map_mode.get() == "single":
            return
        for row in self._infer_rows:
            row["enabled"] = True
        self._refresh_infer_tree()

    def _infer_select_none(self):
        if self.infer_map_mode.get() == "single":
            return
        for row in self._infer_rows:
            row["enabled"] = False
        self._refresh_infer_tree()

    def _on_infer_tree_select(self, _event=None):
        self._on_map_select()

    def _on_infer_tree_click(self, event):
        if self.infer_tree.identify_region(event.x, event.y) != "cell":
            return
        col = self.infer_tree.identify_column(event.x)
        iid = self.infer_tree.identify_row(event.y)
        if not iid:
            return
        if col == "#1":
            self.infer_tree.selection_set(iid)
            self._infer_toggle_selected()
            return "break"
        if col in ("#2", "#3"):
            self._drag_src_iid = iid
            self.infer_tree.selection_set(iid)

    def _on_infer_drag_motion(self, event):
        if not self._drag_src_iid:
            return
        target = self.infer_tree.identify_row(event.y)
        for iid in self.infer_tree.get_children():
            tags = list(self.infer_tree.item(iid, "tags"))
            tags = [t for t in tags if t != "drag_over"]
            self.infer_tree.item(iid, tags=tags)
        if target and target != self._drag_src_iid:
            tags = list(self.infer_tree.item(target, "tags"))
            if "drag_over" not in tags:
                tags.append("drag_over")
            self.infer_tree.item(target, tags=tags)

    def _on_infer_drag_release(self, event):
        if not self._drag_src_iid:
            return
        src = int(self._drag_src_iid)
        target_iid = self.infer_tree.identify_row(event.y)
        self._drag_src_iid = None
        for iid in self.infer_tree.get_children():
            tags = [t for t in self.infer_tree.item(iid, "tags") if t != "drag_over"]
            self.infer_tree.item(iid, tags=tags)
        if not target_iid:
            return
        dst = int(target_iid)
        if src == dst:
            return
        self._infer_reorder(src, dst)

    def _infer_reorder(self, src_idx, dst_idx):
        rows = self._infer_rows
        if src_idx < 0 or src_idx >= len(rows) or dst_idx < 0 or dst_idx >= len(rows):
            return
        item = rows.pop(src_idx)
        rows.insert(dst_idx, item)
        for i, r in enumerate(rows):
            r["order"] = i
        self._refresh_infer_tree()
        self.infer_tree.selection_set(str(dst_idx))
        self.infer_tree.see(str(dst_idx))

    def _build_train_run_config(self):
        mode = self.train_map_mode.get()
        self._save_mode_episode_settings(mode)
        if mode == "single":
            enabled = self._train_enabled_rows()
            if len(enabled) != 1:
                raise ValueError("Chế độ Single — chọn đúng một map (bấm [ ]).")
            row = enabled[0]
            sim = build_sim_map_from_file(row["path"])
            n_ep = self._row_episodes(row, "single")
            return "random", [sim], None, n_ep, None

        enabled = [r for r in self._train_rows if r["enabled"]]
        if not enabled:
            raise ValueError("Chọn ít nhất một map train (bấm ô [ ]).")
        if mode == "curriculum":
            ordered = sorted(enabled, key=lambda r: r["order"])
            sims = [build_sim_map_from_file(r["path"]) for r in ordered]
            goals = [self._row_curriculum_goal(r) for r in ordered]
            total_target = sum(goals)
            return mode, sims, None, total_target, goals
        if mode == "sequential":
            ordered = sorted(enabled, key=lambda r: r["order"])
            plan = []
            sims = []
            for r in ordered:
                sim = build_sim_map_from_file(r["path"])
                plan.append((sim, self._row_episodes(r, "sequential")))
                sims.append(sim)
            total = sum(self._row_episodes(r, "sequential") for r in ordered)
            return mode, sims, plan, total, None
        sims = [build_sim_map_from_file(r["path"]) for r in enabled]
        try:
            n_ep = max(1, int(self.spin_ep.get()))
        except ValueError:
            n_ep = self._episodes_by_mode.get("random", 10000)
        return mode, sims, None, n_ep, None

    def _start_train(self):
        if self._running:
            return
        if not self._map_paths:
            messagebox.showwarning("Train", "Không có map trong map/train/")
            return
        oversized = find_oversized_train_maps()
        if oversized:
            messagebox.showwarning("Train", format_oversized_train_maps_message(oversized))
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
        """Gọi từ tab Tạo map sau khi lưu / xóa map."""
        self.handle_maps_changed(kind, path)

    def handle_maps_changed(self, kind=None, path=None):
        """Cập nhật danh sách map train/infer khi có thay đổi trên đĩa."""
        basename = os.path.basename(path) if path else None
        self.refresh_maps()
        if self._is_busy():
            if basename and (kind is None or kind == self.mode.get()):
                self.status.set("Map cập nhật: %s" % basename)
            return
        if not basename or kind is None:
            return
        if kind == "train":
            for i, row in enumerate(self._train_rows):
                if row["name"] == basename:
                    row["enabled"] = True
                    self._refresh_train_tree()
                    self.train_tree.selection_set(str(i))
                    self.train_tree.see(str(i))
                    break
        elif kind == "infer" and self._map_paths:
            for i, row in enumerate(self._infer_rows):
                if row["name"] == basename:
                    if self.infer_map_mode.get() == "single":
                        for r in self._infer_rows:
                            r["enabled"] = False
                    row["enabled"] = True
                    self._refresh_infer_tree()
                    self.infer_tree.selection_set(str(i))
                    self.infer_tree.see(str(i))
                    break
        if self.view.get() == "map" and (kind is None or kind == self.mode.get()):
            self._preview_map_from_selection()
        if basename and (kind is None or kind == self.mode.get()):
            self.status.set("Đã refresh — map: %s" % basename)

    def _emit_maps_changed(self, kind, path):
        if self._on_maps_changed:
            try:
                self._on_maps_changed(kind, path)
            except Exception:
                pass

    def _step_delay_ms(self):
        try:
            return max(1, int(self.step_delay.get()))
        except ValueError:
            return 200

    def _on_mode_change(self):
        if self._running and self._locked_mode and self.mode.get() != self._locked_mode:
            self.mode.set(self._locked_mode)
            return
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
            self._on_infer_mode_change()
        self._update_view_widgets()

    def _repack_infer_buttons(self):
        self.btn_infer_select_all.pack_forget()
        self.btn_infer_select_none.pack_forget()
        self.btn_infer_delete_map.pack_forget()
        if self.infer_map_mode.get() == "single":
            self.btn_infer_delete_map.pack(side=tk.LEFT, padx=0, pady=4)
        else:
            self.btn_infer_select_all.pack(side=tk.LEFT, padx=(0, 4), pady=4)
            self.btn_infer_select_none.pack(side=tk.LEFT, padx=4, pady=4)
            self.btn_infer_delete_map.pack(side=tk.LEFT, padx=(8, 0), pady=4)

    def _on_infer_mode_change(self):
        if self.mode.get() != "infer":
            return
        mode = self.infer_map_mode.get()
        enabled = [r for r in self._infer_rows if r["enabled"]]
        if mode == "single":
            if len(enabled) > 1:
                keep = enabled[0]
                for r in self._infer_rows:
                    r["enabled"] = r is keep
            elif len(enabled) == 0 and self._infer_rows:
                pick = self._infer_row_by_iid(self.infer_tree.selection()[0]) if self.infer_tree.selection() else self._infer_rows[0]
                if pick:
                    for r in self._infer_rows:
                        r["enabled"] = r is pick
        self._repack_infer_buttons()
        self._refresh_infer_tree()
        active = [i for i, r in enumerate(self._infer_rows) if r["enabled"]]
        if active:
            self.infer_tree.selection_set(str(active[0]))
            self.infer_tree.see(str(active[0]))
        elif self._infer_rows:
            self.infer_tree.selection_set("0")
        if self.view.get() == "map":
            self._preview_map_from_selection()

    def _infer_mode_label(self):
        return "Single" if self.infer_map_mode.get() == "single" else "Sequence"

    def _infer_target_paths(self):
        mode = self.infer_map_mode.get()
        if mode == "single":
            enabled = [r for r in self._infer_rows if r["enabled"]]
            if len(enabled) != 1:
                raise ValueError("Chế độ Single — chọn đúng một map infer (bấm ô [ ]).")
            return [enabled[0]["path"]]
        enabled = [r for r in self._infer_rows if r["enabled"]]
        if not enabled:
            raise ValueError("Chế độ Sequence — chọn ít nhất một map infer (bấm ô [ ]).")
        ordered = sorted(enabled, key=lambda r: r["order"])
        return [r["path"] for r in ordered]

    def _clear_log(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _append_log_text(self, text):
        if not text:
            return
        if not text.endswith("\n"):
            text += "\n"
        self.log.configure(state=tk.NORMAL)
        at_bottom = self.log.yview()[1] >= 0.98
        self.log.insert(tk.END, text)
        if at_bottom:
            self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _format_step_log(self, entry):
        return train_log.format_step_log_entry(entry, include_reward=True) + "\n"

    def _append_step_log(self, entry):
        line = self._format_step_log(entry)
        self.log.configure(state=tk.NORMAL)
        at_bottom = self.log.yview()[1] >= 0.98
        self.log.insert(tk.END, line)
        if at_bottom:
            self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _begin_run(self):
        self._running = True
        self._stop_requested = False
        self._paused = False
        self._locked_view = self.view.get()
        self._locked_mode = self.mode.get()
        self.btn_run.configure(state=tk.DISABLED, text="▶ Run")
        self.btn_pause.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL)
        self.view_group.set_enabled(False)
        self.mode_group.set_enabled(False)

    def _end_run(self):
        self._running = False
        self._stop_requested = False
        self._paused = False
        self._locked_view = None
        self._locked_mode = None
        self._infer_seq_ctx = None
        self.btn_run.configure(state=tk.NORMAL, text="▶ Run")
        self.btn_pause.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.DISABLED)
        self.view_group.set_enabled(True)
        self.mode_group.set_enabled(True)

    def _set_paused_ui(self, paused):
        self._paused = paused
        if paused:
            self.btn_run.configure(state=tk.NORMAL, text="▶ Continue")
            self.btn_pause.configure(state=tk.DISABLED)
            self.status.set("Paused")
            if self.view.get() == "map":
                if self.mode.get() == "train":
                    self.map_view.set_status("Train tạm dừng — bấm Continue để chạy tiếp")
                else:
                    self.map_view.set_status("Inference tạm dừng — bấm Continue để chạy tiếp")
        else:
            self.btn_run.configure(state=tk.DISABLED, text="▶ Run")
            self.btn_pause.configure(state=tk.NORMAL)
            if self.mode.get() == "train":
                self.status.set("Training..." if self.view.get() == "map" else "Running...")
            else:
                self.status.set("Playing..." if self.view.get() == "map" else "Running...")

    def _pause_gate(self):
        import time

        while self._paused and not self._stop_requested:
            time.sleep(0.05)

    def _on_view_change(self):
        if self._running and self._locked_view and self.view.get() != self._locked_view:
            self.view.set(self._locked_view)
            return
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
        sel = self.infer_tree.selection()
        if sel:
            row = self._infer_row_by_iid(sel[0])
            if row:
                for i, path in enumerate(self._map_paths):
                    if path == row["path"]:
                        self._preview_map(i)
                        return
        enabled = [r for r in self._infer_rows if r["enabled"]]
        if enabled:
            target = enabled[0]["path"]
            for i, path in enumerate(self._map_paths):
                if path == target:
                    self._preview_map(i)
                    return
        if self._map_paths:
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
                hint = "%s (%dx%d) — bấm Run để chạy inference"
            self.map_view.set_status(hint % (name, sim["width"], sim["height"]))
            self.status.set("Map loaded")
            self.root.after_idle(self.map_view.redraw)
        except Exception as exc:
            self.map_view.set_status("Lỗi load map: %s" % exc)

    def _update_view_widgets(self):
        self._rebuild_paned_panes()

    def _set_map_hint(self, text):
        text = (text or "").strip()
        if text:
            self.map_hint.configure(text=text)
            if not self.map_hint.winfo_ismapped():
                self.map_hint.pack(anchor=tk.W, pady=(0, px(4)))
        else:
            self.map_hint.pack_forget()

    def refresh_maps(self):
        train_paths = list_map_files("train")
        infer_paths = list_map_files("infer")

        if self.mode.get() == "train":
            self._map_paths = train_paths
            self._sync_train_rows_from_paths()
            self._set_map_hint("")
            self._apply_train_mode_ui()
        else:
            self._map_paths = infer_paths
            self._sync_infer_rows_from_paths()
            self._set_map_hint("")
            self.spin_ep.configure(state=tk.DISABLED)
            # Giữ danh sách train đồng bộ khi đang xem tab infer
            saved_paths = self._map_paths
            self._map_paths = train_paths
            self._sync_train_rows_from_paths()
            self._map_paths = saved_paths
        if self.view.get() == "map":
            self.root.after_idle(self._preview_map_from_selection)

    def _is_busy(self):
        """Đang chạy train/inference và chưa bấm Stop."""
        return self._running and not self._stop_requested

    def refresh_map_view(self):
        """Đọc lại map từ map/train|infer/ và vẽ lại bản đồ đang chọn."""
        if self._is_busy():
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
            sel = self.infer_tree.selection()
            if sel:
                row = self._infer_row_by_iid(sel[0])
                if row:
                    prev_name = row["name"]
        self.refresh_maps()
        if prev_name and self._map_paths:
            if self.mode.get() == "train":
                for i, row in enumerate(self._train_rows):
                    if row["name"] == prev_name:
                        self.train_tree.selection_set(str(i))
                        self.train_tree.see(str(i))
                        break
            else:
                for i, row in enumerate(self._infer_rows):
                    if row["name"] == prev_name:
                        self.infer_tree.selection_set(str(i))
                        self.infer_tree.see(str(i))
                        break
        n = len(self._map_paths)
        if self.view.get() == "map":
            self._preview_map_from_selection()
            self.status.set("Refresh map — %d file trong map/%s/" % (n, kind))
        else:
            self.status.set("Refresh map — %d file trong map/%s/ (chọn View Map để xem)" % (n, kind))
    def _delete_selected_train_map(self):
        if self._is_busy():
            messagebox.showinfo("Xóa map", "Đang chạy train/inference — vui lòng bấm Stop hoặc đợi chạy xong.")
            return
        sel = self.train_tree.selection()
        if not sel:
            messagebox.showinfo("Xóa map", "Vui lòng chọn bản đồ trong danh sách train để xóa.")
            return
        row = self._train_row_by_iid(sel[0])
        if not row:
            return
        filename = row["name"]
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa bản đồ '{filename}' khỏi danh sách train không?",
            icon="warning"
        )
        if not confirm:
            return
        path = os.path.join(maps_dir_for_kind("train"), filename)
        try:
            if os.path.exists(path):
                os.remove(path)
                messagebox.showinfo("Đã xóa", f"Đã xóa thành công bản đồ '{filename}'!")
                self._emit_maps_changed("train", path)
            else:
                messagebox.showerror("Lỗi", f"Không tìm thấy file bản đồ '{filename}' để xóa.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi xóa file: {str(e)}")

    def _delete_selected_infer_map(self):
        if self._is_busy():
            messagebox.showinfo("Xóa map", "Đang chạy train/inference — vui lòng bấm Stop hoặc đợi chạy xong.")
            return
        sel = self.infer_tree.selection()
        if not sel:
            messagebox.showinfo("Xóa map", "Vui lòng chọn bản đồ trong danh sách inference để xóa.")
            return
        row = self._infer_row_by_iid(sel[0])
        if not row:
            return
        path = row["path"]
        filename = row["name"]
        if is_bundled_map_path(path):
            messagebox.showinfo(
                "Xóa map",
                "Map infer mặc định nằm bên trong file .exe nên không thể xóa từ danh sách."
            )
            return
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa bản đồ '{filename}' khỏi danh sách inference không?",
            icon="warning"
        )
        if not confirm:
            return
        try:
            if os.path.exists(path):
                os.remove(path)
                messagebox.showinfo("Đã xóa", f"Đã xóa thành công bản đồ '{filename}'!")
                self._emit_maps_changed("infer", path)
            else:
                messagebox.showerror("Lỗi", f"Không tìm thấy file bản đồ '{filename}' để xóa.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi xóa file: {str(e)}")
    def on_run(self):
        if self._running and self._paused:
            self._set_paused_ui(False)
            return
        if self._running:
            return

        if self.mode.get() == "infer":
            try:
                targets = self._infer_target_paths()
            except ValueError as exc:
                messagebox.showwarning("Inference", str(exc))
                return
            try:
                self._infer_policy_bin()
            except FileNotFoundError as exc:
                messagebox.showwarning("Inference", str(exc))
                return

            if len(targets) == 1:
                idx = self._map_paths.index(targets[0])
                if self.view.get() == "map":
                    self._run_infer_map(idx)
                else:
                    self._run_infer_log(idx)
            else:
                if self.view.get() == "map":
                    self._run_infer_sequence_map(targets)
                else:
                    self._run_infer_sequence(targets)
            return

        self._start_train()

    def _start_queue_processing(self):
        self._ui_queue = queue.Queue()
        self._poll_after_id = self.root.after(20, self._process_ui_queue)

    def _cancel_pending_ui_sync(self):
        """Thoát các lệnh chờ UI (train map) khi bấm Stop."""
        while not self._ui_queue.empty():
            try:
                _fn, evt, _delay_ms = self._ui_queue.get_nowait()
                evt.set()
            except queue.Empty:
                break
            except Exception:
                break
        if self._sync_after_id is not None:
            try:
                self.root.after_cancel(self._sync_after_id)
            except tk.TclError:
                pass
            self._sync_after_id = None
        if self._sync_after_evt is not None:
            self._sync_after_evt.set()
            self._sync_after_evt = None
        if self._current_sync_evt is not None:
            self._current_sync_evt.set()

    def _release_sync_event(self, evt):
        if self._stop_requested:
            evt.set()
            return
        if self._paused:
            self._sync_after_id = self.root.after(50, lambda e=evt: self._release_sync_event(e))
            return
        evt.set()

    def _process_ui_queue(self):
        while not self._ui_queue.empty():
            try:
                fn, evt, delay_ms = self._ui_queue.get_nowait()
            except queue.Empty:
                break

            try:
                if not self._stop_requested:
                    fn()
            except Exception as e:
                print("UI sync error:", e)

            if delay_ms > 0 and not self._stop_requested:
                self._sync_after_evt = evt

                def _release_delayed():
                    self._sync_after_id = None
                    self._sync_after_evt = None
                    self._release_sync_event(evt)

                self._sync_after_id = self.root.after(delay_ms, _release_delayed)
            else:
                self._release_sync_event(evt)

            self._ui_queue.task_done()

        self._poll_after_id = self.root.after(20, self._process_ui_queue)

    def _ui_sync(self, fn):
        """Chạy fn trên main thread và chờ xong (dùng từ thread train)."""
        if self._stop_requested:
            return
        self._pause_gate()
        if self._stop_requested:
            return
        evt = threading.Event()
        self._current_sync_evt = evt
        try:
            self._ui_queue.put((fn, evt, 0))
            evt.wait()
        finally:
            self._current_sync_evt = None

    def _ui_sync_after_delay(self, fn, delay_ms):
        if self._stop_requested:
            return
        self._pause_gate()
        if self._stop_requested:
            return
        evt = threading.Event()
        self._current_sync_evt = evt
        try:
            self._ui_queue.put((fn, evt, delay_ms))
            evt.wait()
        finally:
            self._current_sync_evt = None

    def _ui_async(self, fn):
        """Chạy fn trên main thread — luôn thực thi (kể cả sau Stop, để gọi _end_train)."""
        self.root.after(0, fn)

    def _should_stop_train(self):
        return self._stop_requested

    def on_pause(self):
        if not self._running or self._paused or self._stop_requested:
            return
        self._set_paused_ui(True)

    def on_stop(self):
        if not self._running:
            return
        self._stop_requested = True
        self._paused = False
        self._cancel_pending_ui_sync()
        self.btn_stop.configure(state=tk.DISABLED)
        self.btn_pause.configure(state=tk.DISABLED)
        self.btn_run.configure(state=tk.DISABLED, text="▶ Run")
        if self.mode.get() == "train":
            self.status.set("Stopping...")
            if self.view.get() == "map":
                self.map_view.set_status("Đang dừng train…")
        else:
            if self._anim_after_id:
                self.root.after_cancel(self._anim_after_id)
                self._anim_after_id = None
            if self._infer_seq_ctx:
                self._infer_sequence_finish(stopped=True)
            else:
                self._end_run()
            self.status.set("Stopped")
            if self.view.get() == "map":
                self.map_view.set_status("Inference stopped")


    def _begin_train(self):
        self._begin_run()

    def _end_train(self, stopped=False, episodes_done=0, export_path=None):
        self._end_run()
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

    def _append_infer_session_header(self):
        self._append_log_text(
            "Inference (%s) — %s.\n" % (self._infer_mode_label(), self._infer_scoring_formula_line())
        )

    def _make_train_callbacks(self, n_episodes, animate_map=True):
        def on_episode_start(sim, ep, eps, total):
            if self._stop_requested:
                return

            def show():
                name = sim.get("name", "?")
                if animate_map:
                    self.map_view.load_sim_map(sim)
                    self.map_view.reset_path()
                    self.map_view.set_status(
                        "Episode %d/%d | map: %s | ε=%.3f" % (ep + 1, total, name, eps)
                    )
                self.status.set("Training episode %d/%d" % (ep + 1, total))
                self._append_log_text(
                    "Episode %d/%d | eps=%.3f\n%s\n%s\n"
                    % (
                        ep + 1,
                        total,
                        eps,
                        "\n".join(train_log.format_map_meta_lines(name, sim)),
                        train_log.format_step_log_header(include_reward=True),
                    )
                )

            if animate_map:
                self._ui_sync(show)
            else:
                self._ui_async(show)

        def on_step(entry):
            if self._stop_requested:
                return

            def show():
                if animate_map:
                    self.map_view.show_step(entry)
                self._append_step_log(entry)

            if animate_map:
                self._ui_sync_after_delay(show, self._step_delay_ms())
            else:
                self._ui_async(show)

        return on_episode_start, on_step

    def _run_train_log(self, export_path):
        self._begin_train()
        self._clear_log()
        self.status.set("Running...")

        try:
            mode, sims, plan, n_ep, curriculum_goal_hits = self._build_train_run_config()
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
                    pause_gate=self._pause_gate,
                    checkpoint=self._train_checkpoint_spec(),
                    train_map_mode=mode,
                    train_sims=sims,
                    sequential_plan=plan,
                    curriculum_goal_hits=curriculum_goal_hits,
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
                self._ui_async(lambda s=stopped, e=ep_done, p=out: self._end_train(s, e, p))

        threading.Thread(target=work, daemon=True).start()

    def _run_train_map(self, export_path):
        self._begin_train()
        self._clear_log()
        self.status.set("Training...")
        if self._anim_after_id:
            self.root.after_cancel(self._anim_after_id)
            self._anim_after_id = None

        try:
            mode, sims, plan, n_ep, curriculum_goal_hits = self._build_train_run_config()
        except ValueError as exc:
            messagebox.showwarning("Train", str(exc))
            self._end_train(False, 0)
            return

        on_episode_start, on_step = self._make_train_callbacks(n_ep, animate_map=True)

        def work():
            import rl_runner

            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log, self.root)
            try:
                result = rl_runner.run_train(
                    n_episodes=n_ep,
                    on_episode_start=on_episode_start,
                    on_step=on_step,
                    step_wait=None,
                    should_stop=self._should_stop_train,
                    pause_gate=self._pause_gate,
                    checkpoint=self._train_checkpoint_spec(),
                    train_map_mode=mode,
                    train_sims=sims,
                    sequential_plan=plan,
                    curriculum_goal_hits=curriculum_goal_hits,
                    export_policy_path=export_path,
                )
            except Exception as exc:
                print("ERROR:", exc)
                result = {"stopped": False}
            finally:
                sys.stdout = old_stdout
                stopped = result.get("stopped", False)
                ep_done = result.get("episodes_done", 0)
                out = result.get("export_path", export_path)
                self._ui_async(lambda s=stopped, e=ep_done, p=out: self._end_train(s, e, p))

        threading.Thread(target=work, daemon=True).start()

    def _format_check_infer_report(self, label, sim_map, outcome):
        return self._format_infer_steps_report(label, sim_map, outcome)

    @staticmethod
    def _infer_scoring_formula_line():
        return "scoring: goal +400, checkpoint +100, collision -100, each action -2"

    @staticmethod
    def _format_infer_map_line(map_label, map_score):
        return "- %s: %.1f points" % (map_label, float(map_score))

    @staticmethod
    def _format_infer_total_line(total_score):
        return "Final total score: %.1f" % float(total_score)

    def _format_infer_steps_report(self, map_label, sim_map, outcome):
        return train_log.format_episode_actions_log(
            map_label, sim_map, outcome, include_reward=True, include_end=True
        ).rstrip("\n") + "\n"

    def _format_infer_score_summary(self, map_scores, total_score):
        lines = ["", "=== FINAL SCORE SUMMARY ==="]
        for map_label, map_score in map_scores:
            lines.append(self._format_infer_map_line(map_label, map_score))
        lines.append(self._format_infer_total_line(total_score))
        return "\n".join(lines)

    def _run_check_infer_all(self):
        if self._running:
            return
        try:
            infer_paths = self._infer_target_paths()
        except ValueError as exc:
            messagebox.showwarning("Check infer", str(exc))
            return
        try:
            policy_bin = self._infer_policy_bin()
        except FileNotFoundError as exc:
            messagebox.showwarning("Check infer", str(exc))
            return

        if self.view.get() != "log":
            self.view.set("log")
        self._begin_run()
        self._clear_log()
        self.status.set("Checking infer...")
        self._append_log_text(
            "Check infer (%s) — %s." % (self._infer_mode_label(), self._infer_scoring_formula_line())
        )

        def finish(done, total, stopped=False):
            self._end_run()
            if stopped:
                self.status.set("Stopped - checked %d/%d map(s)" % (done, total))
            else:
                self.status.set("Done - checked %d map(s)" % done)

        def work():
            import rl_runner

            done = 0
            total = len(infer_paths)
            total_score = 0.0
            map_scores = []
            last_sim = None
            last_outcome = None
            try:
                for map_path in infer_paths:
                    if self._stop_requested:
                        break
                    sim, outcome = rl_runner.run_infer_episode_for_map(
                        map_path,
                        verbose=False,
                        policy_bin=policy_bin,
                        pause_gate=self._pause_gate,
                        should_stop=lambda: self._stop_requested,
                    )
                    last_sim = sim
                    last_outcome = outcome
                    done += 1
                    map_label = sim.get("name") or os.path.basename(map_path)
                    map_score = float(outcome.get("score", 0.0))
                    total_score += map_score
                    map_scores.append((map_label, map_score))
                    text = self._format_check_infer_report(map_label, sim, outcome)
                    self._ui_async(lambda t=text: self._append_log_text(t))
                    if outcome.get("status") == "stopped":
                        break
            except Exception as exc:
                self._ui_async(lambda err=exc: self._append_log_text("ERROR: %s" % err))
            finally:
                stopped = bool(self._stop_requested)
                if last_sim is not None and self.view.get() == "map":
                    self._ui_async(lambda s=last_sim, o=last_outcome: self._render_infer_result_map(s, o))
                summary = self._format_infer_score_summary(map_scores, total_score)
                self._ui_async(lambda t=summary: self._append_log_text(t))
                self._ui_async(lambda d=done, t=total, s=stopped: finish(d, t, s))

        threading.Thread(target=work, daemon=True).start()

    def _run_infer_sequence(self, infer_paths):
        if self._running:
            return
        try:
            policy_bin = self._infer_policy_bin()
        except FileNotFoundError as exc:
            messagebox.showwarning("Inference", str(exc))
            return
        self._begin_run()
        self._clear_log()
        self.status.set("Running sequence...")
        self._append_infer_session_header()

        def work():
            import rl_runner

            done = 0
            total = len(infer_paths)
            total_score = 0.0
            map_scores = []
            last_sim = None
            last_outcome = None
            try:
                for map_path in infer_paths:
                    if self._stop_requested:
                        break
                    sim, outcome = rl_runner.run_infer_episode_for_map(
                        map_path,
                        verbose=False,
                        policy_bin=policy_bin,
                        pause_gate=self._pause_gate,
                        should_stop=lambda: self._stop_requested,
                    )
                    last_sim = sim
                    last_outcome = outcome
                    done += 1
                    map_label = sim.get("name") or os.path.basename(map_path)
                    map_score = float(outcome.get("score", 0.0))
                    total_score += map_score
                    map_scores.append((map_label, map_score))
                    text = self._format_infer_steps_report(map_label, sim, outcome)
                    self._ui_async(lambda t=text: self._append_log_text(t))
                    if outcome.get("status") == "stopped":
                        break
            except Exception as exc:
                self._ui_async(lambda err=exc: self._append_log_text("ERROR: %s" % err))
            finally:
                if last_sim is not None and self.view.get() == "map":
                    self._ui_async(lambda s=last_sim, o=last_outcome: self._render_infer_result_map(s, o))
                summary = self._format_infer_score_summary(map_scores, total_score)
                self._ui_async(lambda t=summary: self._append_log_text(t))
                self._ui_async(
                    lambda d=done, t=total: self.status.set(
                        ("Stopped - checked %d/%d map(s)" if self._stop_requested else "Done - checked %d map(s)")
                        % ((d, t) if self._stop_requested else (d,))
                    )
                )
                self._ui_async(self._end_run)

        threading.Thread(target=work, daemon=True).start()

    def _run_infer_sequence_map(self, infer_paths):
        if self._running:
            return
        try:
            policy_bin = self._infer_policy_bin()
        except FileNotFoundError as exc:
            messagebox.showwarning("Inference", str(exc))
            return
        self._begin_run()
        self._clear_log()
        if self._anim_after_id:
            self.root.after_cancel(self._anim_after_id)
            self._anim_after_id = None
        self._infer_seq_ctx = {
            "paths": list(infer_paths),
            "policy_bin": policy_bin,
            "index": 0,
            "map_scores": [],
            "total": len(infer_paths),
        }
        self.status.set("Running sequence...")
        self._append_infer_session_header()
        self._infer_sequence_next_map()

    def _infer_sequence_next_map(self):
        ctx = self._infer_seq_ctx
        if not ctx or self._stop_requested:
            self._infer_sequence_finish(stopped=True)
            return
        idx = ctx["index"]
        total = ctx["total"]
        if idx >= total:
            self._infer_sequence_finish(stopped=False)
            return
        map_path = ctx["paths"][idx]
        policy_bin = ctx["policy_bin"]
        self.status.set("Computing map %d/%d..." % (idx + 1, total))

        def work():
            import rl_runner

            try:
                sim, outcome = rl_runner.run_infer_episode_for_map(
                    map_path,
                    verbose=False,
                    policy_bin=policy_bin,
                    pause_gate=self._pause_gate,
                    should_stop=lambda: self._stop_requested,
                )
                map_label = sim.get("name") or os.path.basename(map_path)
                if self._stop_requested or outcome.get("status") == "stopped":
                    self._ui_async(lambda: self._infer_sequence_finish(stopped=True))
                    return
                self._ui_async(
                    lambda s=sim, o=outcome, m=map_label: self._start_animation(s, o, m, sequence_mode=True)
                )
            except Exception as exc:
                self._ui_async(lambda err=exc: self._infer_error(err))

        threading.Thread(target=work, daemon=True).start()

    def _infer_sequence_finish(self, stopped=False):
        ctx = self._infer_seq_ctx
        self._infer_seq_ctx = None
        map_scores = ctx.get("map_scores", []) if ctx else []
        done = len(map_scores)
        total = ctx.get("total", done) if ctx else done
        if map_scores:
            total_score = sum(score for _, score in map_scores)
            self._append_log_text(self._format_infer_score_summary(map_scores, total_score))
        if stopped:
            self.status.set("Stopped - checked %d/%d map(s)" % (done, total))
        else:
            self.status.set("Done - checked %d map(s)" % done)
        self._end_run()

    def _run_infer_log(self, idx):
        map_path = self._map_paths[idx]
        policy_bin = self._infer_policy_bin()
        self._begin_run()
        self._clear_log()
        self.status.set("Running...")
        self._append_infer_session_header()

        def work():
            import rl_runner

            try:
                sim, outcome = rl_runner.run_infer_episode_for_map(
                    map_path,
                    verbose=False,
                    policy_bin=policy_bin,
                    pause_gate=self._pause_gate,
                    should_stop=lambda: self._stop_requested,
                )
                map_label = sim.get("name") or os.path.basename(map_path)
                detail = self._format_infer_steps_report(map_label, sim, outcome)
                total_score = float(outcome.get("score", 0.0))
                summary = self._format_infer_score_summary([(map_label, total_score)], total_score)
                self._ui_async(lambda t=detail: self._append_log_text(t))
                self._ui_async(lambda t=summary: self._append_log_text(t))
            except Exception as exc:
                self._ui_async(lambda err=exc: self._append_log_text("ERROR: %s" % err))
            finally:
                self._ui_async(self._run_done)

        threading.Thread(target=work, daemon=True).start()

    def _run_infer_map(self, idx):
        map_path = self._map_paths[idx]
        policy_bin = self._infer_policy_bin()
        self._begin_run()
        self._clear_log()
        self._append_infer_session_header()
        self.status.set("Computing path...")
        if self._anim_after_id:
            self.root.after_cancel(self._anim_after_id)
            self._anim_after_id = None

        def work():
            import rl_runner
            try:
                sim, outcome = rl_runner.run_infer_episode_for_map(
                    map_path, verbose=False, policy_bin=policy_bin, pause_gate=self._pause_gate
                )
                map_label = sim.get("name") or os.path.basename(map_path)
                self._ui_async(lambda s=sim, o=outcome, m=map_label: self._start_animation(s, o, m))
            except Exception as exc:
                self._ui_async(lambda err=exc: self._infer_error(err))

        threading.Thread(target=work, daemon=True).start()

    def _infer_error(self, exc):
        self._infer_seq_ctx = None
        self._end_run()
        self.status.set("Error")
        messagebox.showerror("Error", str(exc))

    def _start_animation(self, sim_map, outcome, map_label=None, sequence_mode=False):
        delay = self._step_delay_ms()
        map_label = map_label or sim_map.get("name", "?")

        self.map_view.load_sim_map(sim_map)
        self.map_view.reset_path()
        self.status.set("Playing...")
        self._append_log_text(
            "\n".join(train_log.format_map_meta_lines(map_label, sim_map))
            + "\n"
            + train_log.format_step_log_header(include_reward=True)
        )
        log = outcome.get("log") or []
        self._play_steps(log, 0, outcome, delay, map_label, sequence_mode=sequence_mode)

    def _render_infer_result_map(self, sim_map, outcome):
        self.map_view.load_sim_map(sim_map)
        self.map_view.reset_path()
        log = outcome.get("log") or []
        if log:
            self.map_view.show_step(log[-1])
        status = outcome.get("status", "?")
        steps = int(outcome.get("steps", 0))
        score = float(outcome.get("score", 0.0))
        self.map_view.set_status("Result: %s | steps=%d | score=%.1f" % (status, steps, score))

    def _play_steps(self, log, index, outcome, delay, map_label, sequence_mode=False):
        if self._stop_requested:
            self.map_view.set_status("Inference stopped")
            self.status.set("Stopped")
            if sequence_mode or self._infer_seq_ctx:
                self._infer_sequence_finish(stopped=True)
            else:
                self._end_run()
            return
        if self._paused:
            self._anim_after_id = self.root.after(
                50, lambda: self._play_steps(log, index, outcome, delay, map_label, sequence_mode)
            )
            return
        if index >= len(log):
            status = outcome.get("status", "?")
            steps = outcome.get("steps", 0)
            score = float(outcome.get("score", 0.0))
            if status == "goal":
                msg = "GOAL — %d steps" % steps
            elif status == "collision":
                msg = "COLLISION — stopped at step %d" % steps
            else:
                msg = "Finished: %s (%d steps)" % (status, steps)
            self.map_view.set_status(msg)
            self.status.set("Done — " + msg)
            self._append_log_text(train_log.format_infer_end_reason(status, int(steps)) + "\n")
            if sequence_mode and self._infer_seq_ctx:
                ctx = self._infer_seq_ctx
                ctx["map_scores"].append((map_label, score))
                ctx["index"] += 1
                done = len(ctx["map_scores"])
                self.map_view.set_status("Map %d/%d: %s" % (done, ctx["total"], msg))
                self._infer_sequence_next_map()
                return
            self._append_log_text(self._format_infer_score_summary([(map_label, score)], score))
            self._end_run()
            return

        entry = log[index]
        self.map_view.show_step(entry)
        self._append_step_log(entry)
        self._anim_after_id = self.root.after(
            delay,
            lambda: self._play_steps(log, index + 1, outcome, delay, map_label, sequence_mode),
        )

    def _run_done(self):
        self._end_run()
        self.status.set("Done")

    def set_learn_lab_app(self, app):
        self.learn_lab_app = app

    def refresh_formula_list(self):
        try:
            from RL_lib.formula_store import list_saved_formulas

            self.combo_formula["values"] = list_saved_formulas()
        except Exception:
            pass

    def _sync_formula_combo(self):
        self.refresh_formula_list()
        try:
            from RL_lib import reward_config

            name = (reward_config.get_formula_name() or "").strip()
        except Exception:
            name = ""
        values = self.combo_formula["values"]
        self.formula_var.set(name if name in values else "")

    def _on_formula_selected(self, _event=None):
        name = self.formula_var.get().strip()
        if not name:
            return
        if self.learn_lab_app:
            if not self.learn_lab_app.load_and_compile_formula(name):
                self._sync_formula_combo()
            return
        try:
            from RL_lib.formula_store import load_formula_file, normalize_formula_basename
            from RL_lib import reward_config
            import importlib

            data = load_formula_file(name)
            reward_config.sync_weights_from_elements(data.get("element_weights") or {})
            for k, v in (data.get("thresholds") or {}).items():
                if k in reward_config.REWARD_KEYS:
                    setattr(reward_config, k, v)
            reward_config.set_instance_configs(data.get("instance_configs") or {})
            reward_config.set_total_formula_student(data.get("total_formula") or "")
            reward_config.set_enabled_modules(data.get("enabled_modules") or [])
            norm_name = normalize_formula_basename(name)
            reward_config.set_formula_name(norm_name)

            pc_path = os.path.join(os.path.dirname(reward_config.__file__), "reward_config.py")
            with open(pc_path, "r", encoding="utf-8") as f:
                src = f.read()
            from Ui_app.learn_lab_UI import _patch_line, _patch_enabled_modules, _patch_total_formula, _patch_formula_name

            for k, v in reward_config.get_reward_dict().items():
                if k in reward_config.REWARD_KEYS:
                    src = _patch_line(src, k, v)
            src = _patch_enabled_modules(src, sorted(data.get("enabled_modules") or []))
            src = _patch_total_formula(src, data.get("total_formula") or "")
            src = _patch_formula_name(src, norm_name)
            with open(pc_path, "w", encoding="utf-8") as f:
                f.write(src)
            importlib.reload(reward_config)
            reward_config.set_instance_configs(data.get("instance_configs") or {})
            try:
                import Simulation.robot.trainer as trainer
                importlib.reload(trainer)
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Reward", str(exc))
            self._sync_formula_combo()

    def refresh_ui_scale(self):
        for grp in (
            self.mode_group,
            self.view_group,
            self.delay_group,
            self.train_mode_group,
            self.infer_mode_group,
        ):
            try:
                grp.refresh_scale()
            except Exception:
                pass
        try:
            style_train_treeview(self.train_tree, self.root)
            self.train_tree.configure(height=text_lines(8))
            self.train_tree.column("on", width=px(34), minwidth=px(30), stretch=False)
            self.train_tree.column("ord", width=px(32), minwidth=px(28))
            self.train_tree.column("name", width=px(160), minwidth=px(72))
            self.train_tree.column("eps", width=px(72), minwidth=px(56))
            self._apply_train_mode_ui()
        except tk.TclError:
            pass
        try:
            self.log.configure(height=text_lines(16), font=font(9, family="Monospace"))
        except tk.TclError:
            pass
        try:
            style_train_treeview(self.infer_tree, self.root)
            self.infer_tree.configure(height=text_lines(8))
            self.infer_tree.column("on", width=px(34), minwidth=px(30), stretch=False)
            self.infer_tree.column("ord", width=px(32), minwidth=px(28))
            self.infer_tree.column("name", width=px(160), minwidth=px(72))
        except tk.TclError:
            pass
        try:
            self.workspace.pack_configure(padx=px(8), pady=px(4))
            self._side_col_minsize = px(240)
            self._log_col_minsize = px(220)
            self._map_col_minsize = px(180)
            self._paned.configure(sashwidth=px(6))
            self._apply_pane_minsizes()
        except tk.TclError:
            pass
        try:
            self.spin_ep.configure(width=entry_width(8))
            self.combo_formula.configure(width=entry_width(24))
            self.combo_checkpoint.configure(width=entry_width(22))
            self.combo_export_policy.configure(width=entry_width(22))
            self.combo_infer_policy.configure(width=entry_width(28))
        except tk.TclError:
            pass
        try:
            self.train_cfg_frame.rowconfigure(1, minsize=px(72))
            self.train_cfg_frame.rowconfigure(2, minsize=px(48))
        except tk.TclError:
            pass
        try:
            self.map_view.redraw()
        except Exception:
            pass

    def run(self):
        if self._standalone:
            self.root.mainloop()


def run_app(parent=None, root=None):
    app = RlApp(parent=parent, root=root)
    if parent is None:
        app.run()
    return app
