"""
Tab Learn Lab — map 5×5 + cấu hình state/reward (UX học sinh).
"""

import importlib
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SIM = os.path.join(_ROOT, "Simulation")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

from RL_lib import reward_config
from RL_lib.lab_world import LabWorld5
from RL_lib.lab_registry import (
    STATE_MODULES,
    REWARD_ELEMENTS,
    ELEMENT_WEIGHT_KEY,
    THRESHOLD_LABELS,
    elements_for_module,
    FORMULA_HELP,
)
from RL_lib.student_formula import default_total_formula
from RL_lib.lab_export import export_reward_config_py, export_robot_reward_constants
from RL_lib.rl_core import N_ROWS
from Ui_app.lab_scenario_map import LabScenarioMap5
from Ui_app.formula_builder import FormulaBuilder

# Giá trị mặc định weight theo cục reward (học sinh thấy tên tiếng Việt)
_DEFAULT_WEIGHTS = {
    "R_STEP": -1.0,
    "collision": -20.0,
    "forward_clear": 4.0,
    "goal_trend": 5.0,
    "goal_reached": 100.0,
    "cp_trend": 8.0,
    "checkpoint": 30.0,
    "rotate": -3.0,
    "facing_clear": 5.0,
    "wasted_rotate": -12.0,
    "excess_rotate": -20.0,
    "revisit": -20.0,
    "ping_pong": -20.0,
}


class LearnLabApp:
    def __init__(self, parent=None, root=None):
        if parent is None:
            self.root = tk.Tk()
            self.root.title("SS26 — State & Reward Lab")
            self.container = self.root
            self._standalone = True
        else:
            self.root = root or parent.winfo_toplevel()
            self.container = parent
            self._standalone = False

        self.world = LabWorld5()
        self._module_vars = {}
        self._weight_vars = {}
        self._threshold_vars = {}
        self._module_reward_frames = {}
        self._weight_rows = {}

        self._build_ui()
        self._load_from_module()
        self._refresh_reward_panel()
        self._update_state_display()

    def _build_ui(self):
        paned = ttk.Panedwindow(self.container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=2)

        self.scenario_map = LabScenarioMap5(left, self.world, on_change=self._on_scenario_event)
        self._build_reward_config(right)

        exp = ttk.LabelFrame(self.container, text="Xuất / Apply", padding=4)
        exp.pack(fill=tk.X, padx=6, pady=(0, 6))
        bar = ttk.Frame(exp)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="Copy", command=self._copy_export).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Apply → Train", command=self._apply_to_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Reset mặc định", command=self._reset_defaults).pack(side=tk.LEFT, padx=2)
        self.apply_status = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.apply_status).pack(side=tk.LEFT, padx=8)
        self.export_text = scrolledtext.ScrolledText(exp, height=3, font=("Consolas", 8))
        self.export_text.pack(fill=tk.X)

    def _build_reward_config(self, parent):
        top = ttk.LabelFrame(parent, text="State dùng trong s", padding=8)
        top.pack(fill=tk.X)
        grid = ttk.Frame(top)
        grid.pack(fill=tk.X)
        col = row = 0
        for mod in STATE_MODULES:
            var = tk.BooleanVar(value=True)
            self._module_vars[mod["id"]] = var
            ttk.Checkbutton(
                grid, text=mod["label"], variable=var, command=self._on_modules_changed
            ).grid(row=row, column=col, sticky=tk.W, padx=4, pady=2)
            col += 1
            if col >= 2:
                col, row = 0, row + 1

        bottom = ttk.LabelFrame(parent, text="Reward + công thức", padding=6)
        bottom.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.formula_builder = FormulaBuilder(bottom, on_change=self._on_formula_changed)
        self.formula_builder.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(bottom, text=FORMULA_HELP, foreground="#555", wraplength=360, font=("", 8)).pack(
            anchor=tk.W
        )

        canvas = tk.Canvas(bottom, highlightthickness=0)
        scroll = ttk.Scrollbar(bottom, orient=tk.VERTICAL, command=canvas.yview)
        self._reward_scroll_inner = ttk.Frame(canvas)
        self._reward_scroll_canvas = canvas

        def _on_reward_scroll_configure(event):
            top, _ = canvas.yview()
            canvas.configure(scrollregion=canvas.bbox("all"))
            if top < 1.0:
                canvas.yview_moveto(top)

        def _on_reward_canvas_configure(event):
            canvas.itemconfigure(self._reward_scroll_win, width=event.width)

        self._reward_scroll_inner.bind("<Configure>", _on_reward_scroll_configure)
        self._reward_scroll_win = canvas.create_window((0, 0), window=self._reward_scroll_inner, anchor=tk.NW)
        canvas.bind("<Configure>", _on_reward_canvas_configure)
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(6, 0))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(6, 0))

        ttk.Label(
            self._reward_scroll_inner,
            text="Điểm mỗi cục (0 = tắt). Bật state → thêm nút reward; tự kéo vào công thức.",
            font=("", 8),
            foreground="#555",
        ).pack(anchor=tk.W, pady=(0, 4))

        for mod in STATE_MODULES:
            mid = mod["id"]
            elems = elements_for_module(mid)
            if not elems:
                continue
            box = ttk.LabelFrame(self._reward_scroll_inner, text=mod["label"], padding=6)
            self._module_reward_frames[mid] = box
            for eid in elems:
                meta = REWARD_ELEMENTS[eid]
                row = ttk.Frame(box)
                row.pack(fill=tk.X, pady=2)
                ttk.Label(row, text=meta["label"], width=28).pack(side=tk.LEFT)
                var = tk.StringVar(value=str(_DEFAULT_WEIGHTS.get(eid, 0)))
                self._weight_vars[eid] = var
                ttk.Spinbox(row, from_=-500, to=500, width=8, textvariable=var).pack(side=tk.LEFT, padx=4)
                var.trace_add("write", lambda *_: self._on_weight_edited())
                self._weight_rows[eid] = row

            if mid in ("rotation", "explore_penalty"):
                for tk_key, tk_lbl in THRESHOLD_LABELS.items():
                    if mid == "rotation" and tk_key != "MAX_ROTATE_STREAK":
                        continue
                    if mid == "explore_penalty" and tk_key == "MAX_ROTATE_STREAK":
                        continue
                    tr = ttk.Frame(box)
                    tr.pack(fill=tk.X, pady=2)
                    ttk.Label(tr, text=tk_lbl, width=28).pack(side=tk.LEFT)
                    tv = tk.StringVar(value="4")
                    self._threshold_vars[tk_key] = tv
                    ttk.Spinbox(tr, from_=0, to=50, width=8, textvariable=tv).pack(side=tk.LEFT, padx=4)
                    tv.trace_add("write", lambda *_: self._on_weight_edited())

        self._bind_reward_wheel_tree(self._reward_scroll_canvas)

    def _bind_reward_wheel_tree(self, widget):
        """Cuộn reward chỉ khi con trỏ trong vùng điểm — không bind toàn app."""
        if getattr(widget, "_reward_wheel_tag", False):
            return
        widget._reward_wheel_tag = True

        def _on_reward_wheel(event):
            if self.formula_builder.is_dragging():
                return "break"
            c = self._reward_scroll_canvas
            if event.delta:
                c.yview_scroll(int(-event.delta / 120), "units")
            elif event.num == 4:
                c.yview_scroll(-1, "units")
            elif event.num == 5:
                c.yview_scroll(1, "units")
            return "break"

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(seq, _on_reward_wheel, add="+")

        for child in widget.winfo_children():
            self._bind_reward_wheel_tree(child)

    def _enabled_modules(self):
        return {mid for mid, v in self._module_vars.items() if v.get()}

    def _enabled_labels(self):
        enabled = self._enabled_modules()
        return [REWARD_ELEMENTS[e]["label"] for e, m in REWARD_ELEMENTS.items() if m["module"] in enabled]

    def _on_modules_changed(self):
        reward_config.set_enabled_modules(self._enabled_modules())
        self._refresh_reward_panel()
        self._update_state_display()
        self._refresh_export()

    def _refresh_reward_panel(self):
        enabled = self._enabled_modules()
        labels = self._enabled_labels()
        self.formula_builder.set_labels(labels)

        for mid, box in self._module_reward_frames.items():
            if mid in enabled:
                box.pack(fill=tk.X, pady=4, padx=2)
            else:
                box.pack_forget()
                for eid in elements_for_module(mid):
                    if eid in self._weight_vars:
                        self._weight_vars[eid].set("0")

        self._sync_config_from_ui()
        self._bind_reward_wheel_tree(self._reward_scroll_inner)

    def _collect_element_weights(self):
        out = {}
        for eid, var in self._weight_vars.items():
            raw = var.get().strip()
            try:
                out[eid] = float(raw) if "." in raw else int(raw)
            except ValueError:
                out[eid] = _DEFAULT_WEIGHTS.get(eid, 0)
        return out

    def _collect_thresholds(self):
        out = {}
        for k, var in self._threshold_vars.items():
            try:
                out[k] = int(var.get())
            except ValueError:
                out[k] = reward_config.get_reward_dict().get(k, 0)
        return out

    def _sync_config_from_ui(self):
        weights = self._collect_element_weights()
        reward_config.sync_weights_from_elements(weights)
        for k, v in self._collect_thresholds().items():
            if k in reward_config.REWARD_KEYS:
                setattr(reward_config, k, v)
        reward_config.set_total_formula_student(self.formula_builder.get_expr())

    def _on_weight_edited(self):
        self._sync_config_from_ui()
        self._refresh_export()

    def _on_formula_changed(self):
        self._sync_config_from_ui()
        self._refresh_export()

    def _on_scenario_event(self, action_name):
        self._sync_config_from_ui()
        if action_name:
            self.world.do_action(action_name)
        self._update_state_display()
        self.scenario_map.redraw()

    def _label_for_eid(self, eid):
        return REWARD_ELEMENTS.get(eid, {}).get("label", eid)

    def _update_state_display(self):
        enabled = self._enabled_modules()
        snap = self.world.get_state_snapshot(enabled)
        n, w, e, s = snap["obs"]
        lines = [
            "── STATE ──",
            "Vị trí (%d,%d)  hướng %s" % (snap["pos"][0], snap["pos"][1], snap["heading"]),
            "s = %d" % snap["s"],
        ]
        if "obstacle" in enabled:
            lines.append("Tường nhìn thấy: trước=%d trái=%d phải=%d sau=%d" % (n, w, e, s))
        if "goal" in enabled:
            lines.append("Trend goal: %+d" % snap["goal_trend"])
        if "checkpoint" in enabled:
            lines.append("Trend CP: %s" % snap["cp_trends"])

        if self.world.last_action:
            lines.extend(["", "── REWARD ──", "Công thức: %s" % reward_config.get_total_formula_student()])
            sign = "+" if self.world.last_total >= 0 else ""
            lines.append("TỔNG: %s%.1f điểm" % (sign, self.world.last_total))
            for eid, val in self.world.last_parts.items():
                if val and REWARD_ELEMENTS.get(eid, {}).get("module") in enabled:
                    lines.append("  • %s: %+.1f" % (self._label_for_eid(eid), val))
        else:
            lines.extend(["", "→ Bấm Forward / Rotate trên map"])

        self.scenario_map.set_result_text("\n".join(lines))
        self._refresh_export()

    def _load_from_module(self):
        d = reward_config.get_reward_dict()
        for eid, wkey in ELEMENT_WEIGHT_KEY.items():
            if eid in self._weight_vars and wkey in d:
                self._weight_vars[eid].set(str(d[wkey]))
        for k, var in self._threshold_vars.items():
            if k in d:
                var.set(str(d[k]))
        for mid, var in self._module_vars.items():
            var.set(mid in reward_config.get_enabled_modules())
        self.formula_builder.set_expr(reward_config.get_total_formula_student())

    def _refresh_export(self):
        self._sync_config_from_ui()
        vals = reward_config.get_reward_dict()
        text = (
            "# Công thức học sinh: %s\n" % reward_config.get_total_formula_student()
            + export_reward_config_py(vals)
        )
        self.export_text.delete("1.0", tk.END)
        self.export_text.insert(tk.END, text)

    def _copy_export(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.export_text.get("1.0", tk.END))
        self.apply_status.set("Đã copy")

    def _apply_to_project(self):
        self._sync_config_from_ui()
        vals = reward_config.get_reward_dict()
        enabled = self._enabled_modules()

        pc_path = os.path.join(_ROOT, "RL_lib", "reward_config.py")
        robot_path = os.path.join(_ROOT, "Robot_embbed", "modules", "logics", "reward_config.py")
        src = _read_reward_module_source()
        for k, v in vals.items():
            if k in reward_config.REWARD_KEYS:
                src = _patch_line(src, k, v)
        src = _patch_enabled_modules(src, sorted(enabled))
        src = _patch_total_formula(src, reward_config.get_total_formula_student())
        with open(pc_path, "w", encoding="utf-8") as f:
            f.write(src)
        with open(robot_path, "w", encoding="utf-8") as f:
            f.write(export_robot_reward_constants(vals))

        importlib.reload(reward_config)
        try:
            import Simulation.robot.trainer as trainer
            importlib.reload(trainer)
        except Exception:
            pass
        self.apply_status.set("Đã Apply")
        messagebox.showinfo("Apply", "Đã ghi cấu hình — Train tab dùng ngay.")

    def _reset_defaults(self):
        for mid, var in self._module_vars.items():
            var.set(True)
        for eid, var in self._weight_vars.items():
            var.set(str(_DEFAULT_WEIGHTS.get(eid, 0)))
        for k, var in self._threshold_vars.items():
            var.set(str({"MAX_ROTATE_STREAK": 4, "MAX_NODE_REVISITS": 5, "MAX_PING_PONG_CYCLES": 2}[k]))
        self.formula_builder.set_tokens(default_total_formula(set(self._module_vars.keys())))
        self.world.reset_scenario()
        self.scenario_map.redraw()
        self._on_modules_changed()

    def run(self):
        if self._standalone:
            self.root.mainloop()


def _read_reward_module_source():
    with open(os.path.join(_ROOT, "RL_lib", "reward_config.py"), encoding="utf-8") as f:
        return f.read()


def _patch_line(src, key, value):
    if isinstance(value, bool):
        rep = "%s = %s" % (key, "True" if value else "False")
    elif isinstance(value, float):
        rep = "%s = %s" % (key, value if value != int(value) else "%d.0" % int(value))
    else:
        rep = "%s = %d" % (key, int(value))
    pat = r"^%s\s*=.*$" % re.escape(key)
    if re.search(pat, src, re.MULTILINE):
        return re.sub(pat, rep, src, count=1, flags=re.MULTILINE)
    return src


def _patch_enabled_modules(src, modules):
    return re.sub(
        r"^ENABLED_MODULES\s*=.*$",
        "ENABLED_MODULES = set(%r)" % modules,
        src,
        count=1,
        flags=re.MULTILINE,
    )


def _patch_total_formula(src, expr):
    rep = "TOTAL_FORMULA_STUDENT = %r" % expr
    if re.search(r"^TOTAL_FORMULA_STUDENT\s*=", src, re.MULTILINE):
        return re.sub(r"^TOTAL_FORMULA_STUDENT\s*=.*$", rep, src, count=1, flags=re.MULTILINE)
    return src


def run_app(parent=None, root=None):
    app = LearnLabApp(parent=parent, root=root)
    if parent is None:
        app.run()
    return app
