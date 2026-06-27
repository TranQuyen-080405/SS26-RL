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
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SS26 RL — Train / Infer")
        self.root.minsize(720, 560)

        self.mode = tk.StringVar(value="train")
        self.view = tk.StringVar(value="log")
        self.episodes = tk.IntVar(value=10000)
        self.step_delay = tk.IntVar(value=400)
        self.checkpoint_var = tk.StringVar(value="(mới)")
        self.infer_policy_var = tk.StringVar(value="policy.json")
        self._running = False
        self._stop_requested = False
        self._map_paths = []
        self._anim_after_id = None
        self._ui_done = threading.Event()

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
        bar = ttk.Frame(self.root, padding=8)
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
        self.ck_frame = ttk.Frame(self.root, padding=(8, 4))
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
            text="Train mới hoặc chọn Q_table có sẵn — export luôn ghi đồng bộ .json + .bin",
        ).pack(side=tk.LEFT, padx=8)
        self.refresh_checkpoints()

    def _build_infer_policy_bar(self):
        self.infer_policy_frame = ttk.Frame(self.root, padding=(8, 4))
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
            text="Chọn file Q_table/*.json để infer",
        ).pack(side=tk.LEFT, padx=8)
        self.refresh_infer_policies()

    def refresh_infer_policies(self):
        from robot.policy_io import list_policy_json_files

        prev = self.infer_policy_var.get()
        files = list_policy_json_files()
        self.combo_infer_policy["values"] = files
        if prev in files:
            self.infer_policy_var.set(prev)
        elif "policy.json" in files:
            self.infer_policy_var.set("policy.json")
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

    def _infer_policy_json(self):
        from robot.policy_io import policy_json_path

        name = self.infer_policy_var.get().strip()
        if not name:
            raise FileNotFoundError("Chọn file policy .json trong Q_table/")
        path = policy_json_path(name)
        if not os.path.isfile(path):
            raise FileNotFoundError("Không tìm thấy policy: %s" % path)
        return path

    def _build_map_list(self):
        self.maps_frame = ttk.LabelFrame(self.root, text="Maps", padding=8)
        self.maps_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 4))
        frame = self.maps_frame

        self.map_hint = ttk.Label(frame, text="")
        self.map_hint.pack(anchor=tk.W, pady=(0, 4))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.map_list = tk.Listbox(list_frame, height=5, yscrollcommand=scroll.set, selectmode=tk.BROWSE)
        scroll.config(command=self.map_list.yview)
        self.map_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.map_list.bind("<<ListboxSelect>>", self._on_map_select)

    def _build_content(self):
        self.content = ttk.Frame(self.root)
        self.content.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.log_frame = ttk.LabelFrame(self.content, text="Output", padding=8)
        self.log = scrolledtext.ScrolledText(self.log_frame, height=16, state=tk.DISABLED, font=("Monospace", 10))
        self.log.pack(fill=tk.BOTH, expand=True)

        self.map_frame = ttk.LabelFrame(self.content, text="Map", padding=8)
        self.map_view = SimMapCanvas(self.map_frame)
        self.map_view.pack(fill=tk.BOTH, expand=True)

    def _build_actions(self):
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill=tk.X)
        self.btn_run = ttk.Button(bar, text="Run", command=self.on_run)
        self.btn_run.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(bar, text="Stop", command=self.on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        self.status = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.status).pack(side=tk.LEFT, padx=12)

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
            self.refresh_checkpoints()
        else:
            self.ck_frame.pack_forget()
            self.infer_policy_frame.pack(fill=tk.X, before=self.maps_frame)
            self.refresh_infer_policies()
        self._update_view_widgets()

    def _on_view_change(self):
        self._update_view_widgets()

    def _on_map_select(self, _event=None):
        if self.view.get() == "map" and not self._running:
            self._preview_map_from_selection()

    def _preview_map_from_selection(self):
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
        self.map_list.delete(0, tk.END)
        for path in self._map_paths:
            self.map_list.insert(tk.END, os.path.basename(path))
        if self.mode.get() == "train":
            self.map_hint.config(
                text="Train học trên tất cả map/train/. Chọn file để xem layout; Map + Run để xem robot train."
            )
            self.spin_ep.configure(state=tk.NORMAL)
        else:
            self.map_hint.config(text="Infer: chọn map. Map + Run để xem robot infer từng bước.")
            self.spin_ep.configure(state=tk.DISABLED)
        if self._map_paths:
            self.map_list.selection_set(0)
        if self.view.get() == "map":
            self.root.after_idle(self._preview_map_from_selection)

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
                self._infer_policy_json()
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

        def work():
            import rl_runner

            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log, self.root)
            try:
                try:
                    n_ep = int(self.spin_ep.get())
                except ValueError:
                    n_ep = rl_runner.N_EPISODES_DEFAULT
                result = rl_runner.run_train(
                    n_episodes=n_ep,
                    should_stop=self._should_stop_train,
                    checkpoint=self._train_checkpoint_spec(),
                )
            except Exception as exc:
                print("ERROR:", exc)
                result = {"stopped": False}
            finally:
                sys.stdout = old_stdout
                stopped = result.get("stopped", False) if isinstance(result, dict) else False
                ep_done = result.get("episodes_done", 0) if isinstance(result, dict) else 0
                self.root.after(0, lambda: self._end_train(stopped, ep_done))

        threading.Thread(target=work, daemon=True).start()

    def _run_train_map(self):
        self._begin_train()
        self.status.set("Training...")
        if self._anim_after_id:
            self.root.after_cancel(self._anim_after_id)
            self._anim_after_id = None

        try:
            n_ep = int(self.spin_ep.get())
        except ValueError:
            import rl_runner

            n_ep = rl_runner.N_EPISODES_DEFAULT

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
                )
                stopped = result.get("stopped", False)
                ep_done = result.get("episodes_done", 0)
                self.root.after(0, lambda: self._end_train(stopped, ep_done))
            except Exception as exc:
                self.root.after(0, lambda: self._infer_error(exc))

        threading.Thread(target=work, daemon=True).start()

    def _run_infer_log(self, idx):
        map_path = self._map_paths[idx]
        policy_json = self._infer_policy_json()
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
                print("policy:", policy_json)
                print("---")
                sim, outcome = rl_runner.run_infer_episode_for_map(
                    map_path, verbose=True, policy_json=policy_json
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
        policy_json = self._infer_policy_json()
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
                    map_path, verbose=False, policy_json=policy_json
                )
                self.root.after(0, lambda: self._start_animation(sim, outcome))
            except Exception as exc:
                self.root.after(0, lambda: self._infer_error(exc))

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
        self.root.mainloop()


def run_app():
    RlApp().run()
