"""
Tab Learn Lab — map 12×5 + cấu hình state/reward (UX học sinh).
"""

import importlib
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext

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
    FORMULA_HELP,
)
from RL_lib.student_formula import default_total_formula
from RL_lib.lab_export import export_reward_config_py
from RL_lib.rl_core import N_ROWS
from Ui_app.lab_scenario_map import LabScenarioMap5
from Ui_app.formula_builder import FormulaBuilder, module_chip_style, reward_eids_in_formula

_THRESHOLD_FOR_EID = {
    "excess_rotate": "MAX_ROTATE_STREAK",
    "revisit": "MAX_NODE_REVISITS",
    "ping_pong": "MAX_PING_PONG_CYCLES",
}

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

_REWARD_DESCRIPTIONS = {
    "collision": "Robot đâm vào tường",
    "forward_clear": "Đi thẳng 1 ô an toàn",
    "goal_trend": "Đi gần/xa Goal",
    "goal_reached": "Chạm ô Goal",
    "cp_trend": "Đi gần/xa Checkpoint",
    "checkpoint": "Đi đến checkpoint (chỉ tính một lần)",
    "rotate": "Mỗi lần xoay hướng",
    "facing_clear": "Xoay sang hướng không có vật cản",
    "wasted_rotate": "Xoay tại chỗ liên tục",
    "excess_rotate": "Phạt khi xoay liên tiếp vượt quá ngưỡng",
    "revisit": "Đi vào một ô quá nhiều lần",
    "ping_pong": "Đi qua lại 2 ô liên tục",
    "MAX_ROTATE_STREAK": "Ngưỡng xoay",
    "MAX_NODE_REVISITS": "Số lần đi vào 1 ô",
    "MAX_PING_PONG_CYCLES": "Số lần đi qua lại",
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
        self._weight_rows = {}
        self._threshold_rows = {}
        self._save_after_id = None
        self._loading = False

        self._build_ui()
        self._loading = True
        self._load_from_module()
        self._loading = False
        self._refresh_reward_panel()
        self._update_state_display()

    def _build_ui(self):
        main_layout = ttk.Frame(self.container)
        main_layout.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        left = ttk.Frame(main_layout)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        right = ttk.Frame(main_layout)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scenario_map = LabScenarioMap5(left, self.world, on_change=self._on_scenario_event)
        self._build_reward_config(right)

        exp = ttk.LabelFrame(self.container, text="Xuất cấu hình", padding=4)
        exp.pack(fill=tk.X, padx=6, pady=(0, 6))
        bar = ttk.Frame(exp)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="Copy", command=self._copy_export).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Reset mặc định", command=self._reset_defaults).pack(side=tk.LEFT, padx=2)
        self.apply_status = tk.StringVar(value="Bấm nút 'Lưu công thức' để lưu cấu hình và áp dụng cho Train")
        ttk.Label(bar, textvariable=self.apply_status).pack(side=tk.LEFT, padx=8)
        self.export_text = scrolledtext.ScrolledText(exp, height=3, font=("Consolas", 8))
        self.export_text.pack(fill=tk.X)

    def _build_reward_config(self, parent):
        top = ttk.LabelFrame(parent, text="State dùng", padding=8)
        top.pack(fill=tk.X)
        grid = ttk.Frame(top)
        grid.pack(fill=tk.X)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        col = row = 0
        for mod in STATE_MODULES:
            var = tk.BooleanVar(value=True)
            self._module_vars[mod["id"]] = var
            chip = module_chip_style(mod["id"])
            tk.Checkbutton(
                grid,
                text=mod["label"],
                variable=var,
                command=self._on_modules_changed,
                bg=chip["bg"],
                fg=chip["fg"],
                activebackground=chip.get("active", chip["bg"]),
                activeforeground=chip["fg"],
                selectcolor="#ffffff",
                padx=6,
                pady=2,
                font=("", 9, "bold"),
                anchor=tk.W,
                relief=tk.FLAT,
                bd=0,
            ).grid(row=row, column=col, sticky=tk.W + tk.E, padx=4, pady=4)
            col += 1
            if col >= 2:
                col, row = 0, row + 1

        bottom = ttk.LabelFrame(parent, text="Công thức Reward", padding=6)
        bottom.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.formula_builder = FormulaBuilder(bottom, on_change=self._on_formula_changed)
        self.formula_builder.pack(fill=tk.X, pady=(0, 6))

        # Nút Lưu công thức
        self.btn_save_formula = ttk.Button(bottom, text="Lưu công thức", command=self._save_to_project)
        self.btn_save_formula.pack(anchor=tk.W, pady=(0, 4))

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

        # ttk.Label(
        #     self._reward_scroll_inner,
        #     text="Điểm mỗi cục trong công thức (0 = tắt) — màu khớp chip reward:",
        #     font=("", 8),
        #     foreground="#555",
        # ).pack(anchor=tk.W, pady=(0, 4))

        self._weights_container = ttk.Frame(self._reward_scroll_inner)
        self._weights_container.pack(fill=tk.X)

        for eid, meta in REWARD_ELEMENTS.items():
            mod = meta["module"]
            chip = module_chip_style(mod)
            row = tk.Frame(self._weights_container, bg=chip["bg"], padx=6, pady=4)
            self._weight_rows[eid] = row
            tk.Label(
                row,
                text=meta["label"],
                bg=chip["bg"],
                fg=chip["fg"],
                font=("", 9, "bold"),
                anchor=tk.W,
                width=28,
            ).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(_DEFAULT_WEIGHTS.get(eid, 0)))
            self._weight_vars[eid] = var
            ttk.Spinbox(row, from_=-500, to=500, width=8, textvariable=var).pack(side=tk.LEFT, padx=4)
            var.trace_add("write", lambda *_: self._on_weight_edited())
            desc = _REWARD_DESCRIPTIONS.get(eid, "")
            tk.Label(
                row,
                text="—  " + desc,
                bg=chip["bg"],
                fg=chip["fg"],
                font=("", 9, "italic"),
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=(12, 0))

        for eid, tk_key in _THRESHOLD_FOR_EID.items():
            if tk_key not in THRESHOLD_LABELS:
                continue
            mod = REWARD_ELEMENTS[eid]["module"]
            chip = module_chip_style(mod)
            tr = tk.Frame(self._weights_container, bg=chip["bg"], padx=6, pady=4)
            self._threshold_rows[tk_key] = tr
            tk.Label(
                tr,
                text=THRESHOLD_LABELS[tk_key],
                bg=chip["bg"],
                fg=chip["fg"],
                font=("", 9),
                anchor=tk.W,
                width=28,
            ).pack(side=tk.LEFT)
            tv = tk.StringVar(value="4")
            self._threshold_vars[tk_key] = tv
            ttk.Spinbox(tr, from_=0, to=50, width=8, textvariable=tv).pack(side=tk.LEFT, padx=4)
            tv.trace_add("write", lambda *_: self._on_weight_edited())
            desc = _REWARD_DESCRIPTIONS.get(tk_key, "")
            tk.Label(
                tr,
                text="—  " + desc,
                bg=chip["bg"],
                fg=chip["fg"],
                font=("", 9, "italic"),
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=(12, 0))

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

    def _formula_reward_eids(self):
        return reward_eids_in_formula(self.formula_builder.get_tokens())

    def _refresh_weight_panel(self):
        eids = self._formula_reward_eids()
        eid_set = set(eids)

        for row in self._weight_rows.values():
            row.pack_forget()
        for tr in self._threshold_rows.values():
            tr.pack_forget()

        for eid in eids:
            row = self._weight_rows.get(eid)
            if row:
                row.pack(fill=tk.X, pady=2, padx=2)
            tk_key = _THRESHOLD_FOR_EID.get(eid)
            if tk_key and tk_key in self._threshold_rows and eid in eid_set:
                self._threshold_rows[tk_key].pack(fill=tk.X, pady=(0, 2), padx=2)



    def _on_modules_changed(self):
        enabled_modules = self._enabled_modules()
        reward_config.set_enabled_modules(enabled_modules)
        
        # Remove rewards belonging to disabled modules from formula builder
        allowed_labels = {meta["label"] for meta in REWARD_ELEMENTS.values() if meta["module"] in enabled_modules}
        tokens = self.formula_builder.get_tokens()
        filtered_tokens = [t for t in tokens if t["kind"] != "reward" or t["value"] in allowed_labels]
        self.formula_builder.set_tokens(filtered_tokens)

        self._refresh_reward_panel()
        self._update_state_display()
        self._refresh_export()

    def _refresh_reward_panel(self):
        labels = self._enabled_labels()
        self.formula_builder.set_labels(labels)
        self._sync_config_from_ui()
        self._refresh_weight_panel()
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
        self._refresh_weight_panel()
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
        state_rows = [
            "Vị trí (%d,%d)  hướng %s" % (snap["pos"][0], snap["pos"][1], snap["heading"]),
            "s = %d" % snap["s"],
        ]
        if "obstacle" in enabled:
            state_rows.append(
                "Tường nhìn thấy: trước=%d trái=%d phải=%d sau=%d" % (n, w, e, s)
            )
        if "goal" in enabled:
            state_rows.append("Trend goal: %+d" % snap["goal_trend"])
        if "checkpoint" in enabled:
            state_rows.append("Trend CP: %s" % snap["cp_trends"])

        has_action = bool(self.world.last_action)
        parts = []
        if has_action:
            for eid in self._formula_reward_eids():
                val = self.world.last_parts.get(eid, 0)
                if not val:
                    continue
                style = module_chip_style(REWARD_ELEMENTS[eid]["module"])
                parts.append((self._label_for_eid(eid), style["bg"], style["fg"], val))

        self.scenario_map.set_result_display(
            state_rows=state_rows,
            has_action=has_action,
            action_name=self.world.last_action or "",
            formula=self.formula_builder.get_expr(),
            total=self.world.last_total,
            parts=parts,
        )
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

    def _schedule_save_to_project(self):
        if self._loading:
            return
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(400, self._save_to_project)

    def _save_to_project(self):
        self._save_after_id = None
        try:
            self._sync_config_from_ui()
            vals = reward_config.get_reward_dict()
            enabled = self._enabled_modules()

            pc_path = os.path.join(_ROOT, "RL_lib", "reward_config.py")
            src = _read_reward_module_source()
            for k, v in vals.items():
                if k in reward_config.REWARD_KEYS:
                    src = _patch_line(src, k, v)
            src = _patch_enabled_modules(src, sorted(enabled))
            src = _patch_total_formula(src, reward_config.get_total_formula_student())
            with open(pc_path, "w", encoding="utf-8") as f:
                f.write(src)

            importlib.reload(reward_config)
            try:
                import Simulation.robot.trainer as trainer
                importlib.reload(trainer)
            except Exception:
                pass
            self.apply_status.set("Đã lưu — Train tab dùng ngay")
        except Exception as exc:
            self.apply_status.set("Lỗi lưu: %s" % exc)

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
