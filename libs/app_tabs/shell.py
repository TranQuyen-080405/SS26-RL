"""SS26-RL — shell 4 tab."""

import tkinter as tk
from tkinter import ttk

from Ui_app.ui_scale import attach_window_scaling, configure_window, font, init as init_ui_scale, px
from app_tabs.robot_monitor import RobotMonitorApp

# (nhãn, nền chưa chọn, nền khi chọn)
_TAB_COLORS = (
    ("Edit Map", "#3d5240", "#a6e3a1"),
    ("Edit State", "#524a32", "#f9e2af"),
    ("Train / Inference", "#32405a", "#89b4fa"),
    ("Monitor", "#45325a", "#cba6f7"),
)


class _ColoredNotebook:
    """Thanh tab màu + vùng nội dung (không dùng ttk.Notebook — tránh tab lặp trên Windows)."""

    def __init__(self, parent):
        self._parent = parent
        self._bar = tk.Frame(parent, bg="#11111b", padx=px(6), pady=px(6))
        self._bar.pack(fill=tk.X)
        self._body = ttk.Frame(parent)
        self._body.pack(fill=tk.BOTH, expand=True)
        self._buttons = []
        self._frames = []
        self._active = None
        self._tab_meta = []

    def refresh_scale(self):
        self._bar.configure(padx=px(6), pady=px(6))
        f = font(10, weight="bold")
        for btn, _idle, _active in self._buttons:
            btn.configure(padx=px(18), pady=px(9), font=f)

    def add(self, label, bg_idle, bg_active):
        frame = ttk.Frame(self._body)
        idx = len(self._frames)
        self._frames.append(frame)
        btn = tk.Button(
            self._bar,
            text=label,
            bg=bg_idle,
            fg="#cdd6f4",
            activebackground=bg_active,
            activeforeground="#11111b",
            relief=tk.RAISED,
            bd=2,
            padx=px(18),
            pady=px(9),
            font=font(10, weight="bold"),
            cursor="hand2",
            command=lambda i=idx: self.select(i),
        )
        btn.pack(side=tk.LEFT, padx=px(3))
        self._buttons.append((btn, bg_idle, bg_active))
        self._tab_meta.append((label, bg_idle, bg_active))
        return frame

    def select(self, idx):
        if idx < 0 or idx >= len(self._frames):
            return
        if self._active is not None and self._active < len(self._frames):
            self._frames[self._active].pack_forget()
        self._frames[idx].pack(fill=tk.BOTH, expand=True)
        self._active = idx
        self._paint_buttons(idx)

    def _paint_buttons(self, active_idx):
        for i, (btn, idle, active) in enumerate(self._buttons):
            if i == active_idx:
                btn.configure(bg=active, fg="#11111b", relief=tk.RAISED, bd=2)
            else:
                btn.configure(bg=idle, fg="#cdd6f4", relief=tk.RAISED, bd=2)


class SS26App:
    def __init__(self, initial_tab=0):
        self.root = tk.Tk()
        self.root.title("SS26-RL")
        init_ui_scale(self.root)
        configure_window(self.root, width=1200, height=720, min_width=800, min_height=500)

        self._monitor = None
        self._tabs = None
        self._build_ui(initial_tab)
        attach_window_scaling(self.root, self._on_ui_scale_changed)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_ui_scale_changed(self):
        if self._tabs is not None:
            self._tabs.refresh_scale()
        try:
            self.learn_lab_app.refresh_ui_scale()
        except Exception:
            pass
        try:
            self.rl_app.refresh_ui_scale()
        except Exception:
            pass
        try:
            self._map_editor.redraw()
        except Exception:
            pass
        try:
            if self._monitor is not None:
                self._monitor.map_view.redraw()
        except Exception:
            pass

    def _build_ui(self, initial_tab):
        tabs = _ColoredNotebook(self.root)
        self._tabs = tabs

        tab_map = tabs.add(*_TAB_COLORS[0])
        tab_lab = tabs.add(*_TAB_COLORS[1])
        tab_rl = tabs.add(*_TAB_COLORS[2])
        tab_robot = tabs.add(*_TAB_COLORS[3])

        from Ui_app.create_map_UI import MapEditorApp
        from Ui_app.rl_app_UI import RlApp
        from Ui_app.learn_lab_UI import LearnLabApp

        self.rl_app = RlApp(parent=tab_rl, root=self.root)
        self._map_editor = MapEditorApp(parent=tab_map, root=self.root, on_saved=self.rl_app.notify_map_saved)
        self.learn_lab_app = LearnLabApp(parent=tab_lab, root=self.root)
        self.rl_app.set_learn_lab_app(self.learn_lab_app)
        self._monitor = RobotMonitorApp(parent=tab_robot, root=self.root)

        if 0 <= initial_tab < 4:
            tabs.select(initial_tab)
        else:
            tabs.select(0)

    def _on_close(self):
        if self._monitor is not None:
            try:
                self._monitor.disconnect()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_app(initial_tab=0):
    SS26App(initial_tab=initial_tab).run()


def main():
    from map.map_io import MAP_ROOT, TRAIN_MAPS_DIR, INFER_MAPS_DIR, list_map_files

    print("SS26-RL app")
    print("MAP_ROOT:", MAP_ROOT)
    print("  train:", len(list_map_files("train")), "file(s) ->", TRAIN_MAPS_DIR)
    print("  infer:", len(list_map_files("infer")), "file(s) ->", INFER_MAPS_DIR)
    run_app(initial_tab=0)
