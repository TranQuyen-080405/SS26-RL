"""
Tab Learn Lab — map 12×5 + cấu hình state/reward (UX học sinh).
"""

import importlib
import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox

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
from RL_lib.formula_store import (
    build_snapshot,
    ensure_formula_dir,
    list_saved_formulas,
    load_formula_file,
    normalize_formula_basename,
    save_formula_file,
    delete_formula_file,
)
from RL_lib.rl_core import N_ROWS
from Ui_app.lab_scenario_map import LabScenarioMap5
from Ui_app.formula_builder import FormulaBuilder, module_chip_style, reward_eids_in_formula
from Ui_app.ui_scale import entry_width, font, px

_THRESHOLD_FOR_EID = {
    "excess_rotate": "MAX_ROTATE_STREAK",
    "visit_window": "MAX_REVISIT_STEPS",
    "visit_repeat": "MAX_CELL_REPEAT",
    "ping_pong": ["MAX_PING_PONG_CYCLES", "MAX_PING_PONG_SPAN"],
    "straight_streak_reach": "MAX_STRAIGHT_REACH",
    "straight_streak_cap": "MAX_STRAIGHT_CAP",
}

# Giá trị mặc định weight theo cục reward (học sinh thấy tên tiếng Việt)
_DEFAULT_WEIGHTS = {
    "R_STEP": 0.0,
    "collision": 0.0,
    "forward_clear": 0.0,
    "wall_detected": 0.0,
    "wall_visible": 0.0,
    "goal_closer": 0.0,
    "goal_farther": 0.0,
    "goal_reached": 0.0,
    "cp_closer": 0.0,
    "cp_farther": 0.0,
    "checkpoint": 0.0,
    "rotate": 0.0,
    "facing_clear": 0.0,
    "wasted_rotate": 0.0,
    "blocked_rotate": 0.0,
    "excess_rotate": 0.0,
    "visit_window": 0.0,
    "visit_repeat": 0.0,
    "ping_pong": 0.0,
    "straight_streak_reach": 0.0,
    "straight_streak_cap": 0.0,
}

_REWARD_DESCRIPTIONS = {
    "collision": "Robot va chạm tường",
    "forward_clear": "Tiến lên ô không có vật cản",
    "wall_detected": "Phát hiện có vật cản ngay trước mặt sau hành động",
    "wall_visible": "Nhìn thấy tường ở bất kỳ hướng nào xung quanh robot",
    "goal_closer": "Khoảng cách Manhattan tới đích giảm",
    "goal_farther": "Khoảng cách Manhattan tới đích tăng",
    "goal_reached": "Đứng tại ô Goal",
    "cp_closer": "Khoảng cách tới checkpoint chưa ăn giảm",
    "cp_farther": "Khoảng cách tới checkpoint chưa ăn tăng",
    "checkpoint": "Đến Checkpoint lần đầu",
    "rotate": "Hành động xoay hướng",
    "facing_clear": "Hướng mặt về ô không vật cản sau khi xoay",
    "wasted_rotate": "Xoay hướng khi đường phía trước trống",
    "blocked_rotate": "Xoay hướng khi đường phía trước bị chặn",
    "excess_rotate": "Số lần xoay liên tiếp vượt quá ngưỡng",
    "visit_window": "Vào lại cùng một ô trong vòng N bước gần nhất",
    "visit_repeat": "Số lần quay lại ô đã từng đi qua vượt ngưỡng (không tính lần đầu)",
    "ping_pong": "Đi qua-lại cùng một đoạn đường (palindrome); chỉnh Ô mỗi chiều cho đường dài 2–5 ô",
    "straight_streak_reach": "Số lần giữ nguyên hướng đi liên tiếp vượt quá ngưỡng",
    "straight_streak_cap": "Số lần giữ nguyên hướng đi liên tiếp chưa vượt quá ngưỡng",
    "MAX_ROTATE_STREAK": "Ngưỡng xoay",
    "MAX_REVISIT_STEPS": "Số bước",
    "MAX_CELL_REPEAT": "Lần quay lại",
    "MAX_PING_PONG_CYCLES": "Số lần được phép đi lặp qua lại",
    "MAX_PING_PONG_SPAN": "Số ô tối đa mỗi chiều tính được tính là lặp lại",
    "MAX_STRAIGHT_REACH": "Ngưỡng giữ hướng",
    "MAX_STRAIGHT_CAP": "Ngưỡng không giữ hướng",
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
        self._loaded_formula_name = None
        self._scaled_font_widgets = []
        self._scaled_spinboxes = []

        self._build_ui()
        self._loading = True
        self._load_from_module()
        self._loading = False
        self._refresh_reward_panel()
        self._update_state_display()
        self._refresh_move_gate()

    def _refresh_move_gate(self):
        self.scenario_map.set_move_enabled(self.formula_builder.is_valid())

    def _build_ui(self):
        main_layout = ttk.Frame(self.container)
        main_layout.pack(fill=tk.BOTH, expand=True, padx=px(6), pady=px(6))
        self._main_layout = main_layout

        cols = ttk.Frame(main_layout)
        cols.pack(fill=tk.BOTH, expand=True)
        cols.columnconfigure(0, weight=1, uniform="lab_cols")
        cols.columnconfigure(1, weight=3, uniform="lab_cols")
        cols.rowconfigure(0, weight=1)
        self._cols = cols
        self._cols_resize_after = None

        left_outer = ttk.Frame(cols)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(0, px(4)))
        left_scroll = tk.Canvas(left_outer, highlightthickness=0, borderwidth=0)
        left_sb = ttk.Scrollbar(left_outer, orient=tk.VERTICAL, command=left_scroll.yview)
        left_scroll.configure(yscrollcommand=left_sb.set)
        left_sb.pack(side=tk.RIGHT, fill=tk.Y)
        left_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left = ttk.Frame(left_scroll)
        self._left_scroll = left_scroll
        self._left_win = left_scroll.create_window((0, 0), window=left, anchor=tk.NW)

        def _on_left_inner_configure(_event):
            left_scroll.configure(scrollregion=left_scroll.bbox("all"))

        def _on_left_canvas_configure(event):
            left_scroll.itemconfigure(self._left_win, width=event.width)

        left.bind("<Configure>", _on_left_inner_configure)
        left_scroll.bind("<Configure>", _on_left_canvas_configure)

        right = ttk.Frame(cols)
        right.grid(row=0, column=1, sticky="nsew", padx=(px(4), 0))

        self.apply_status = tk.StringVar(
            value="Bấm 'Lưu công thức' để lưu file JSON và áp dụng cho Train"
        )
        self.export_text = None

        self.scenario_map = LabScenarioMap5(left, self.world, on_change=self._on_scenario_event)
        self._bind_left_wheel(left)
        self._build_reward_config(right)
        cols.bind("<Configure>", self._on_lab_cols_configure)
        self.root.after_idle(self._redraw_lab_map)

    def _bind_left_wheel(self, widget):
        if getattr(widget, "_lab_wheel_tag", False):
            return
        widget._lab_wheel_tag = True

        def _on_wheel(event):
            c = self._left_scroll
            if event.delta:
                c.yview_scroll(int(-event.delta / 120), "units")
            elif event.num == 4:
                c.yview_scroll(-1, "units")
            elif event.num == 5:
                c.yview_scroll(1, "units")
            return "break"

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(seq, _on_wheel, add="+")
        for child in widget.winfo_children():
            self._bind_left_wheel(child)

    def _on_lab_cols_configure(self, event=None):
        if event is not None and event.widget is not self._cols:
            return
        if self._cols_resize_after is not None:
            try:
                self.root.after_cancel(self._cols_resize_after)
            except tk.TclError:
                pass
        self._cols_resize_after = self.root.after(80, self._redraw_lab_map)

    def _redraw_lab_map(self):
        self._cols_resize_after = None
        try:
            self.scenario_map.redraw()
        except (tk.TclError, AttributeError):
            pass

        # exp = ttk.LabelFrame(self.container, text="Xuất cấu hình", padding=4)
        # exp.pack(fill=tk.X, padx=6, pady=(0, 6))
        # bar = ttk.Frame(exp)
        # bar.pack(fill=tk.X)
        # ttk.Button(bar, text="Copy", command=self._copy_export).pack(side=tk.LEFT, padx=2)
        # ttk.Button(bar, text="Reset mặc định", command=self._reset_defaults).pack(side=tk.LEFT, padx=2)
        # ttk.Label(bar, textvariable=self.apply_status).pack(side=tk.LEFT, padx=8)
        # self.export_text = scrolledtext.ScrolledText(exp, height=3, font=("Consolas", 8))
        # self.export_text.pack(fill=tk.X)

    def _build_reward_config(self, parent):
        top = ttk.LabelFrame(parent, text="State dùng", padding=8)
        top.pack(fill=tk.X)
        grid = ttk.Frame(top)
        grid.pack(fill=tk.X)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        col = row = 0
        self._scaled_font_widgets = []
        self._scaled_spinboxes = []
        for mod in STATE_MODULES:
            var = tk.BooleanVar(value=True)
            self._module_vars[mod["id"]] = var
            chip = module_chip_style(mod["id"])
            cb = tk.Checkbutton(
                grid,
                text=mod["label"],
                variable=var,
                command=self._on_modules_changed,
                bg=chip["bg"],
                fg=chip["fg"],
                activebackground=chip.get("active", chip["bg"]),
                activeforeground=chip["fg"],
                selectcolor="#ffffff",
                padx=px(6),
                pady=px(2),
                font=font(9, weight="bold"),
                anchor=tk.W,
                relief=tk.FLAT,
                bd=0,
            )
            cb.grid(row=row, column=col, sticky=tk.W + tk.E, padx=4, pady=4)
            self._scaled_font_widgets.append((cb, 9, "bold"))
            col += 1
            if col >= 2:
                col, row = 0, row + 1

        bottom = ttk.LabelFrame(parent, text="Công thức Reward", padding=6)
        bottom.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.formula_builder = FormulaBuilder(bottom, on_change=self._on_formula_changed)
        self.formula_builder.pack(fill=tk.X, pady=(0, 6))

        formula_bar = ttk.Frame(bottom)
        formula_bar.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(formula_bar, text="Đã lưu:").pack(side=tk.LEFT, padx=(0, 4))
        self.formula_pick_var = tk.StringVar()
        self.formula_combo = ttk.Combobox(
            formula_bar,
            textvariable=self.formula_pick_var,
            width=entry_width(28),
            state="readonly",
        )
        self.formula_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.formula_combo.bind("<<ComboboxSelected>>", self._on_formula_pick_selected)
        ttk.Button(formula_bar, text="Nạp", command=self._load_selected_formula).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(formula_bar, text="Làm mới danh sách", command=self._refresh_formula_combo).pack(side=tk.LEFT, padx=(0, 8))
        self.btn_save_formula = ttk.Button(formula_bar, text="Lưu công thức", command=self._save_to_project)
        self.btn_save_formula.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_delete_formula = ttk.Button(formula_bar, text="Xóa công thức", command=self._delete_selected_formula)
        self.btn_delete_formula.pack(side=tk.LEFT)
        ttk.Label(formula_bar, textvariable=self.apply_status, foreground="#555").pack(
            side=tk.LEFT, padx=(12, 0)
        )

        ensure_formula_dir()
        self._refresh_formula_combo()

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
            name_lbl = tk.Label(
                row,
                text=meta["label"],
                bg=chip["bg"],
                fg=chip["fg"],
                font=font(9, weight="bold"),
                anchor=tk.W,
                width=entry_width(28),
            )
            name_lbl.pack(side=tk.LEFT)
            self._scaled_font_widgets.append((name_lbl, 9, "bold"))
            var = tk.StringVar(value=str(_DEFAULT_WEIGHTS.get(eid, 0)))
            self._weight_vars[eid] = var
            w_spin = ttk.Spinbox(row, from_=-500, to=500, width=entry_width(8), textvariable=var)
            w_spin.pack(side=tk.LEFT, padx=px(4))
            self._scaled_spinboxes.append((w_spin, 8))
            var.trace_add("write", lambda *_: self._on_weight_edited())
            desc = _REWARD_DESCRIPTIONS.get(eid, "")
            desc_lbl = tk.Label(
                row,
                text="—  " + desc,
                bg=chip["bg"],
                fg=chip["fg"],
                font=font(9, weight="italic"),
                anchor=tk.W,
            )
            desc_lbl.pack(side=tk.LEFT, padx=(12, 0))
            self._scaled_font_widgets.append((desc_lbl, 9, "italic"))

        for eid, tk_keys in _THRESHOLD_FOR_EID.items():
            keys = tk_keys if isinstance(tk_keys, list) else [tk_keys]
            for tk_key in keys:
                if tk_key not in THRESHOLD_LABELS:
                    continue
                mod = REWARD_ELEMENTS[eid]["module"]
                chip = module_chip_style(mod)
                tr = tk.Frame(self._weights_container, bg=chip["bg"], padx=6, pady=4)
                self._threshold_rows[tk_key] = tr
                th_lbl = tk.Label(
                    tr,
                    text=THRESHOLD_LABELS[tk_key],
                    bg=chip["bg"],
                    fg=chip["fg"],
                    font=font(9),
                    anchor=tk.W,
                    width=entry_width(28),
                )
                th_lbl.pack(side=tk.LEFT)
                self._scaled_font_widgets.append((th_lbl, 9, "normal"))
                tv = tk.StringVar(value="4")
                self._threshold_vars[tk_key] = tv
                t_spin = ttk.Spinbox(tr, from_=0, to=50, width=entry_width(8), textvariable=tv)
                t_spin.pack(side=tk.LEFT, padx=px(4))
                self._scaled_spinboxes.append((t_spin, 8))
                tv.trace_add("write", lambda *_: self._on_weight_edited())
                desc = _REWARD_DESCRIPTIONS.get(tk_key, "")
                th_desc = tk.Label(
                    tr,
                    text="—  " + desc,
                    bg=chip["bg"],
                    fg=chip["fg"],
                    font=font(9, weight="italic"),
                    anchor=tk.W,
                )
                th_desc.pack(side=tk.LEFT, padx=(12, 0))
                self._scaled_font_widgets.append((th_desc, 9, "italic"))

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
            if tk_key:
                keys = tk_key if isinstance(tk_key, list) else [tk_key]
                for k in keys:
                    if k in self._threshold_rows and eid in eid_set:
                        self._threshold_rows[k].pack(fill=tk.X, pady=(0, 2), padx=2)



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
        self._refresh_move_gate()

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
        self._refresh_move_gate()

    def _on_scenario_event(self, action_name):
        if action_name and not self.formula_builder.is_valid():
            return
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
                "Tường nhìn thấy: N=%d W=%d E=%d S=%d" % (n, w, e, s)
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
        if not self.export_text:
            return
        self._sync_config_from_ui()
        vals = reward_config.get_reward_dict()
        text = (
            "# Công thức học sinh: %s\n" % reward_config.get_total_formula_student()
            + export_reward_config_py(vals)
        )
        self.export_text.delete("1.0", tk.END)
        self.export_text.insert(tk.END, text)

    def _collect_formula_snapshot(self):
        weights = self._collect_element_weights()
        thresholds = self._collect_thresholds()
        return build_snapshot(
            self._enabled_modules(),
            self.formula_builder.get_expr(),
            weights,
            thresholds,
        )

    def _refresh_formula_combo(self, select_name=None):
        names = list_saved_formulas()
        self.formula_combo["values"] = names
        pick = select_name or self._loaded_formula_name or self.formula_pick_var.get()
        if pick and pick in names:
            self.formula_pick_var.set(pick)
        elif names:
            self.formula_pick_var.set(names[0])
        else:
            self.formula_pick_var.set("")

    def _on_formula_pick_selected(self, _event=None):
        pass

    def _load_selected_formula(self):
        name = self.formula_pick_var.get().strip()
        if not name:
            messagebox.showinfo("Nạp công thức", "Chưa có file trong thư mục reward_formula/.")
            return
        try:
            self._apply_formula_snapshot(load_formula_file(name))
            self._loaded_formula_name = normalize_formula_basename(name)
            reward_config.set_formula_name(self._loaded_formula_name)
            self.apply_status.set("Đã nạp: %s — chỉnh rồi bấm Lưu công thức" % self._loaded_formula_name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("Nạp công thức", str(exc))

    def _delete_selected_formula(self):
        name = self.formula_pick_var.get().strip()
        if not name:
            messagebox.showinfo("Xóa công thức", "Chưa chọn file công thức nào để xóa.")
            return
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa file công thức '{name}' không?",
            icon="warning"
        )
        if not confirm:
            return
        try:
            if delete_formula_file(name):
                messagebox.showinfo("Đã xóa", f"Đã xóa thành công file công thức '{name}'!")
                if self._loaded_formula_name == name:
                    self._loaded_formula_name = ""
                    reward_config.set_formula_name("")
                    self.apply_status.set("Đã xóa file hiện tại.")
                self._refresh_formula_combo()
            else:
                messagebox.showerror("Lỗi", f"Không tìm thấy file công thức '{name}' để xóa.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi xóa file: {str(e)}")

    def load_and_compile_formula(self, name):
        """Nạp công thức từ file và compile/apply vào dự án (reward_config.py)."""
        try:
            data = load_formula_file(name)
            self._apply_formula_snapshot(data)
            self._loaded_formula_name = normalize_formula_basename(name)
            reward_config.set_formula_name(self._loaded_formula_name)
            self._refresh_formula_combo(select_name=self._loaded_formula_name)

            # Ghi đè cấu hình vào file reward_config.py
            vals = reward_config.get_reward_dict()
            enabled = self._enabled_modules()

            pc_path = os.path.join(_ROOT, "RL_lib", "reward_config.py")
            src = _read_reward_module_source()
            for k, v in vals.items():
                if k in reward_config.REWARD_KEYS:
                    src = _patch_line(src, k, v)
            src = _patch_enabled_modules(src, sorted(enabled))
            src = _patch_total_formula(src, reward_config.get_total_formula_student())
            src = _patch_formula_name(src, self._loaded_formula_name)
            with open(pc_path, "w", encoding="utf-8") as f:
                f.write(src)

            importlib.reload(reward_config)
            try:
                import Simulation.robot.trainer as trainer
                importlib.reload(trainer)
            except Exception:
                pass

            self.apply_status.set("Đã áp dụng công thức: %s" % self._loaded_formula_name)
            return True
        except Exception as exc:
            messagebox.showerror("Nạp công thức", "Lỗi nạp công thức: %s" % exc, parent=self.root)
            return False

    def _apply_formula_snapshot(self, data):
        from RL_lib.formula_store import migrate_formula_snapshot

        data = migrate_formula_snapshot(data)
        self._loading = True
        try:
            modules = set(data.get("enabled_modules") or [])
            if not modules:
                modules = set(self._module_vars.keys())
            for mid, var in self._module_vars.items():
                var.set(mid in modules)

            weights = data.get("element_weights") or {}
            for eid, var in self._weight_vars.items():
                if eid in weights:
                    var.set(str(weights[eid]))

            thresholds = data.get("thresholds") or {}
            for k, var in self._threshold_vars.items():
                if k in thresholds:
                    var.set(str(thresholds[k]))

            expr = data.get("total_formula") or ""
            self.formula_builder.set_labels(self._enabled_labels())
            self.formula_builder.set_expr(expr)
            self._on_modules_changed()
        finally:
            self._loading = False

    def _ask_formula_save_name(self):
        default = self._loaded_formula_name or self.formula_pick_var.get().strip() or "cong_thuc_moi"
        name = simpledialog.askstring(
            "Lưu công thức",
            "Tên file (không cần .json):",
            initialvalue=default,
            parent=self.root,
        )
        if name is None:
            return None
        try:
            return normalize_formula_basename(name)
        except ValueError as exc:
            messagebox.showerror("Lưu công thức", str(exc), parent=self.root)
            return None

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
        if not self.formula_builder.is_valid():
            messagebox.showwarning(
                "Lưu công thức",
                "Công thức chưa hợp lệ — sửa khung đỏ trước khi lưu.",
                parent=self.root,
            )
            return
        save_name = self._ask_formula_save_name()
        if not save_name:
            return
        try:
            self._sync_config_from_ui()
            snapshot = self._collect_formula_snapshot()
            json_path = save_formula_file(save_name, snapshot)
            self._loaded_formula_name = save_name
            self._refresh_formula_combo(select_name=save_name)

            vals = reward_config.get_reward_dict()
            enabled = self._enabled_modules()

            pc_path = os.path.join(_ROOT, "RL_lib", "reward_config.py")
            src = _read_reward_module_source()
            for k, v in vals.items():
                if k in reward_config.REWARD_KEYS:
                    src = _patch_line(src, k, v)
            src = _patch_enabled_modules(src, sorted(enabled))
            src = _patch_total_formula(src, reward_config.get_total_formula_student())
            src = _patch_formula_name(src, save_name)
            with open(pc_path, "w", encoding="utf-8") as f:
                f.write(src)

            reward_config.set_formula_name(save_name)
            importlib.reload(reward_config)
            try:
                import Simulation.robot.trainer as trainer
                importlib.reload(trainer)
            except Exception:
                pass
            self.apply_status.set(
                "Đã lưu %s + áp dụng Train — %s"
                % (os.path.basename(json_path), save_name)
            )
        except Exception as exc:
            self.apply_status.set("Lỗi lưu: %s" % exc)
            messagebox.showerror("Lưu công thức", str(exc), parent=self.root)

    def _reset_defaults(self):
        for mid, var in self._module_vars.items():
            var.set(True)
        for eid, var in self._weight_vars.items():
            var.set(str(_DEFAULT_WEIGHTS.get(eid, 0)))
        for k, var in self._threshold_vars.items():
            var.set(str({
                "MAX_ROTATE_STREAK": 4,
                "MAX_REVISIT_STEPS": 5,
                "MAX_CELL_REPEAT": 3,
                "MAX_PING_PONG_CYCLES": 1,
                "MAX_PING_PONG_SPAN": 5,
                "MAX_STRAIGHT_REACH": 3,
                "MAX_STRAIGHT_CAP": 3,
            }.get(k, var.get())))
        self.formula_builder.set_tokens(default_total_formula(set(self._module_vars.keys())))
        self.world.reset_scenario()
        self.scenario_map.redraw()
        self._on_modules_changed()
        self._loaded_formula_name = ""
        reward_config.set_formula_name("")

    def refresh_ui_scale(self):
        try:
            self._main_layout.pack_configure(padx=px(6), pady=px(6))
        except (tk.TclError, AttributeError):
            pass
        for w, sz, wt in self._scaled_font_widgets:
            try:
                opts = {"font": font(sz, weight=wt)}
                if isinstance(w, tk.Checkbutton):
                    opts["padx"] = px(6)
                    opts["pady"] = px(2)
                w.configure(**opts)
            except tk.TclError:
                pass
        for spin, cw in self._scaled_spinboxes:
            try:
                spin.configure(width=entry_width(cw))
            except tk.TclError:
                pass
        for row in self._weight_rows.values():
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    try:
                        wval = child.cget("width")
                        if wval and int(wval) > 1:
                            child.configure(width=entry_width(28))
                    except (tk.TclError, ValueError):
                        pass
        for tr in self._threshold_rows.values():
            for child in tr.winfo_children():
                if isinstance(child, tk.Label):
                    try:
                        wval = child.cget("width")
                        if wval and int(wval) > 1:
                            child.configure(width=entry_width(28))
                    except (tk.TclError, ValueError):
                        pass
        try:
            self.formula_combo.configure(width=entry_width(28))
        except tk.TclError:
            pass
        try:
            self.formula_builder.refresh_scale()
        except Exception:
            pass
        try:
            self.scenario_map.redraw()
        except Exception:
            pass

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


def _patch_formula_name(src, name):
    rep = "FORMULA_NAME = %r" % name
    if re.search(r"^FORMULA_NAME\s*=", src, re.MULTILINE):
        return re.sub(r"^FORMULA_NAME\s*=.*$", rep, src, count=1, flags=re.MULTILINE)
    return src


def run_app(parent=None, root=None):
    app = LearnLabApp(parent=parent, root=root)
    if parent is None:
        app.run()
    return app
