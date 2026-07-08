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
    DEFAULT_ENABLED_MODULES,
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
from Ui_app.ui_chips import RoundedBlock, build_reward_title, chip_container_bg, split_reward_display
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
_DEFAULT_BLOCK_WEIGHT = 1.0
_DEFAULT_WEIGHTS = {eid: _DEFAULT_BLOCK_WEIGHT for eid in REWARD_ELEMENTS}

_REWARD_DESCRIPTIONS = {
    "collision": "Robot va chạm tường",
    "forward_clear": "Tiến lên ô không có vật cản",
    "wall_detected": "Phát hiện tường lần đầu — phải quay/tiến để nhìn hướng đó (mỗi ô+hướng 1 lần)",
    "wall_visible": "Xoay hướng có tường ngay trước mặt (mỗi lần xoay đều cộng)",
    "wall_on_entry": "Tiến vào ô — state tường (memory) tại ô có ≥1 hướng đã biết; cộng mỗi lần vào ô",
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
    "straight_streak_cap": "Số lần giữ nguyên hướng đi liên tiếp còn ngắn (<= ngưỡng)",
    "MAX_ROTATE_STREAK": "Ngưỡng xoay",
    "MAX_REVISIT_STEPS": "Số bước",
    "MAX_CELL_REPEAT": "Lần quay lại",
    "MAX_PING_PONG_CYCLES": "Số lần được phép đi lặp qua lại",
    "MAX_PING_PONG_SPAN": "Số ô tối đa mỗi chiều tính được tính là lặp lại",
    "MAX_STRAIGHT_REACH": "Ngưỡng giữ hướng",
    "MAX_STRAIGHT_CAP": "Ngưỡng giữ hướng ngắn",
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
        self._weight_vars = {}
        self._threshold_vars = {}
        self._weight_rows = {}
        self._threshold_rows = {}
        self._weight_instance_vars = {}
        self._weight_instance_rows = []
        self._active_reward_instance_keys = []
        self._weight_instance_saved_values = {}
        self._threshold_instance_vars = {}
        self._threshold_instance_rows = []
        self._active_threshold_instance_keys = []
        self._threshold_instance_saved_values = {}
        self._save_after_id = None
        self._formula_fx_after_id = None
        self._weight_panel_sig = None
        self._loading = False
        self._loaded_formula_name = None
        self._rl_app = None
        self._scaled_font_widgets = []
        self._scaled_spinboxes = []
        self._weight_row_widgets = {}
        self._threshold_row_widgets = {}
        self._empty_weight_hint = None

        self._build_ui()
        self._lab_tab_key_bind = self.root.bind("<KeyPress>", self._on_lab_tab_key_press, add="+")
        self._loading = True
        self._load_from_module()
        self._loading = False
        self._refresh_reward_panel()
        self._update_state_display()
        self._refresh_move_gate()

    def set_rl_app(self, app):
        self._rl_app = app

    def _notify_formula_applied(self):
        if self._rl_app is not None:
            try:
                self._rl_app._sync_formula_combo()
            except Exception:
                pass

    def _refresh_move_gate(self):
        self.scenario_map.set_move_enabled(self.formula_builder.is_valid())

    def _on_lab_tab_key_press(self, event):
        try:
            if not self.container.winfo_ismapped():
                return
        except tk.TclError:
            return
        return self.scenario_map.handle_key_event(event)

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

        self.apply_status = tk.StringVar(value="")
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
        self._scaled_font_widgets = []
        self._scaled_spinboxes = []

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

        self._weights_container = tk.Frame(self._reward_scroll_inner, bg=chip_container_bg())
        self._weights_container.pack(fill=tk.X)

        # Biến ẩn — chỉ dùng làm giá trị gợi ý khi nạp công thức (UI theo từng block trong công thức).
        self._weight_vars = {}
        for eid in REWARD_ELEMENTS:
            self._weight_vars[eid] = tk.StringVar(value=str(_DEFAULT_WEIGHTS.get(eid, _DEFAULT_BLOCK_WEIGHT)))

        seen_thresholds = set()
        self._threshold_vars = {}
        for tk_keys in _THRESHOLD_FOR_EID.values():
            keys = tk_keys if isinstance(tk_keys, list) else [tk_keys]
            for tk_key in keys:
                if tk_key in THRESHOLD_LABELS and tk_key not in seen_thresholds:
                    seen_thresholds.add(tk_key)
                    self._threshold_vars[tk_key] = tk.StringVar(value="4")

        self._bind_reward_wheel_tree(self._reward_scroll_canvas)

    def _bind_reward_wheel_tree(self, widget):
        """Cuộn reward chỉ khi con trỏ trong vùng điểm — không bind toàn app."""
        if not getattr(widget, "_reward_wheel_tag", False):
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
        return set(DEFAULT_ENABLED_MODULES)

    def _enabled_labels(self):
        return [REWARD_ELEMENTS[e]["label"] for e in REWARD_ELEMENTS]

    def _formula_reward_eids(self):
        return reward_eids_in_formula(self.formula_builder.get_tokens())

    def _reward_instance_id(self, eid, idx):
        return "%s#%d" % (eid, idx)

    def _threshold_instance_id(self, eid, idx, tk_key):
        return "%s#%d:%s" % (eid, idx, tk_key)

    def _weight_seed_value(self, eid, idx):
        iid = self._reward_instance_id(eid, idx)
        if iid in self._weight_instance_saved_values:
            return self._weight_instance_saved_values[iid]
        if idx == 1:
            base_var = self._weight_vars.get(eid)
            if base_var is not None:
                raw = base_var.get().strip()
                try:
                    return float(raw) if "." in raw else int(raw)
                except ValueError:
                    pass
        return _DEFAULT_WEIGHTS.get(eid, _DEFAULT_BLOCK_WEIGHT)

    def _threshold_seed_value(self, eid, idx, tk_key):
        iid = self._threshold_instance_id(eid, idx, tk_key)
        if iid in self._threshold_instance_saved_values:
            return self._threshold_instance_saved_values[iid]
        if idx == 1:
            base_var = self._threshold_vars.get(tk_key)
            if base_var is not None:
                try:
                    return int(base_var.get())
                except ValueError:
                    pass
        return reward_config.get_reward_dict().get(tk_key, 0)

    def _token_eid(self, tok, label_to_eid):
        base, _ = split_reward_display(tok.get("display") or tok.get("value") or "")
        val = (tok.get("value") or base).strip()
        return label_to_eid.get(val) or label_to_eid.get(base)

    def _formula_instance_signature(self):
        label_to_eid = {meta["label"]: eid for eid, meta in REWARD_ELEMENTS.items()}
        reward_tokens = [t for t in self.formula_builder.get_tokens() if t.get("kind") == "reward"]
        seen_count = {}
        keys = []
        for tok in reward_tokens:
            eid = self._token_eid(tok, label_to_eid)
            if not eid:
                continue
            seen_count[eid] = seen_count.get(eid, 0) + 1
            keys.append((eid, seen_count[eid]))
        return tuple(keys)

    def _create_weight_instance_row(self, eid, idx, w_var):
        mod = REWARD_ELEMENTS[eid]["module"]
        chip = module_chip_style(mod)
        wrap = tk.Frame(self._weights_container, bg=chip_container_bg())
        wr = RoundedBlock(wrap, bg=chip["bg"], canvas_bg=chip_container_bg(), stretch_width=True)
        wr.pack(fill=tk.X)
        inner = wr.inner

        title_row, _ = build_reward_title(
            inner,
            REWARD_ELEMENTS[eid]["label"],
            idx,
            chip["bg"],
            chip["fg"],
            font_size=9,
        )
        title_row.pack(side=tk.LEFT, padx=6, pady=4)
        self._scaled_font_widgets.append((title_row, 9, "bold"))

        w_spin = ttk.Spinbox(inner, from_=-500, to=500, width=entry_width(8), textvariable=w_var)
        w_spin.pack(side=tk.LEFT, padx=px(4), pady=4)
        self._scaled_spinboxes.append((w_spin, 8))

        w_desc = tk.Label(
            inner,
            text="—  " + _REWARD_DESCRIPTIONS.get(eid, ""),
            bg=chip["bg"],
            fg=chip["fg"],
            font=font(9, weight="italic"),
            anchor=tk.W,
        )
        w_desc.pack(side=tk.LEFT, padx=(12, 0), pady=4)
        self._scaled_font_widgets.append((w_desc, 9, "italic"))
        return {"wrap": wrap, "block": wr}

    def _create_threshold_instance_row(self, eid, idx, tk_key, var):
        mod = REWARD_ELEMENTS[eid]["module"]
        chip = module_chip_style(mod)
        wrap = tk.Frame(self._weights_container, bg=chip_container_bg())
        tr = RoundedBlock(wrap, bg=chip["bg"], canvas_bg=chip_container_bg(), stretch_width=True)
        tr.pack(fill=tk.X)
        inner = tr.inner

        title_row, _ = build_reward_title(
            inner,
            REWARD_ELEMENTS[eid]["label"],
            idx,
            chip["bg"],
            chip["fg"],
            font_size=9,
        )
        title_row.pack(side=tk.LEFT, padx=6, pady=4)
        th_suffix = tk.Label(
            title_row,
            text=" — %s" % THRESHOLD_LABELS[tk_key],
            bg=chip["bg"],
            fg=chip["fg"],
            font=font(9),
            anchor=tk.W,
        )
        th_suffix.pack(side=tk.LEFT)
        self._scaled_font_widgets.append((title_row, 9, "normal"))

        t_spin = ttk.Spinbox(inner, from_=0, to=50, width=entry_width(8), textvariable=var)
        t_spin.pack(side=tk.LEFT, padx=px(4), pady=4)
        self._scaled_spinboxes.append((t_spin, 8))

        desc = _REWARD_DESCRIPTIONS.get(tk_key, "")
        th_desc = tk.Label(
            inner,
            text="—  " + desc,
            bg=chip["bg"],
            fg=chip["fg"],
            font=font(9, weight="italic"),
            anchor=tk.W,
        )
        th_desc.pack(side=tk.LEFT, padx=(12, 0), pady=4)
        self._scaled_font_widgets.append((th_desc, 9, "italic"))
        return {"wrap": wrap, "block": tr}

    def _clear_weight_panel_widgets(self):
        for rec in self._weight_row_widgets.values():
            try:
                rec["wrap"].destroy()
            except tk.TclError:
                pass
        for rec in self._threshold_row_widgets.values():
            try:
                rec["wrap"].destroy()
            except tk.TclError:
                pass
        self._weight_row_widgets = {}
        self._threshold_row_widgets = {}
        self._weight_instance_rows = []
        self._threshold_instance_rows = []
        if self._empty_weight_hint is not None:
            try:
                self._empty_weight_hint.destroy()
            except tk.TclError:
                pass
            self._empty_weight_hint = None

    def _refresh_weight_panel(self):
        sig = self._formula_instance_signature()
        if sig == self._weight_panel_sig:
            if sig and self._weight_instance_rows:
                return
            if not sig and self._empty_weight_hint is not None:
                try:
                    if self._empty_weight_hint.winfo_manager():
                        return
                except tk.TclError:
                    pass
        self._weight_panel_sig = sig
        self._weight_instance_rows = []
        self._active_reward_instance_keys = []
        self._threshold_instance_rows = []
        self._active_threshold_instance_keys = []
        self._weight_rows = {}

        label_to_eid = {meta["label"]: eid for eid, meta in REWARD_ELEMENTS.items()}
        reward_tokens = [t for t in self.formula_builder.get_tokens() if t.get("kind") == "reward"]
        for rec in self._weight_row_widgets.values():
            rec["wrap"].pack_forget()
        for rec in self._threshold_row_widgets.values():
            rec["wrap"].pack_forget()
        if not reward_tokens:
            if self._empty_weight_hint is None:
                self._empty_weight_hint = tk.Label(
                    self._weights_container,
                    text="Thêm block reward vào công thức ở trên để chỉnh điểm từng block (#1, #2, …).",
                    bg=chip_container_bg(),
                    fg="#6c7086",
                    font=font(9, "italic"),
                    anchor=tk.W,
                    justify=tk.LEFT,
                )
            self._empty_weight_hint.pack(fill=tk.X, padx=8, pady=8)
            return
        if self._empty_weight_hint is not None:
            self._empty_weight_hint.pack_forget()

        seen_count = {}
        for tok in reward_tokens:
            eid = self._token_eid(tok, label_to_eid)
            if not eid:
                continue

            seen_count[eid] = seen_count.get(eid, 0) + 1
            idx = seen_count[eid]
            iid = self._reward_instance_id(eid, idx)
            self._active_reward_instance_keys.append((eid, idx))

            w_var = self._weight_instance_vars.get((eid, idx))
            if w_var is None:
                w_var = tk.StringVar(value=str(self._weight_seed_value(eid, idx)))
                w_var.trace_add("write", lambda *_: self._on_weight_edited())
                self._weight_instance_vars[(eid, idx)] = w_var

            rec = self._weight_row_widgets.get((eid, idx))
            if rec is None:
                rec = self._create_weight_instance_row(eid, idx, w_var)
                self._weight_row_widgets[(eid, idx)] = rec
            rec["wrap"].pack(fill=tk.X, pady=2, padx=2)
            self._weight_instance_rows.append(rec["block"])

            tk_keys = _THRESHOLD_FOR_EID.get(eid)
            if not tk_keys:
                continue
            keys = tk_keys if isinstance(tk_keys, list) else [tk_keys]
            for tk_key in keys:
                if tk_key not in THRESHOLD_LABELS:
                    continue
                row_key = (eid, idx, tk_key)
                self._active_threshold_instance_keys.append(row_key)

                var = self._threshold_instance_vars.get(row_key)
                if var is None:
                    var = tk.StringVar(value=str(self._threshold_seed_value(eid, idx, tk_key)))
                    var.trace_add("write", lambda *_: self._on_weight_edited())
                    self._threshold_instance_vars[row_key] = var

                rec = self._threshold_row_widgets.get(row_key)
                if rec is None:
                    rec = self._create_threshold_instance_row(eid, idx, tk_key, var)
                    self._threshold_row_widgets[row_key] = rec
                rec["wrap"].pack(fill=tk.X, pady=(0, 2), padx=2)
                self._threshold_instance_rows.append(rec["block"])

        active_weight_keys = set(self._active_reward_instance_keys)
        for key in list(self._weight_instance_vars):
            if key not in active_weight_keys:
                del self._weight_instance_vars[key]
        active_threshold_keys = set(self._active_threshold_instance_keys)
        for key in list(self._threshold_instance_vars):
            if key not in active_threshold_keys:
                del self._threshold_instance_vars[key]
        for key in list(self._weight_row_widgets):
            if key not in active_weight_keys:
                try:
                    self._weight_row_widgets[key]["wrap"].destroy()
                except tk.TclError:
                    pass
                del self._weight_row_widgets[key]
        for key in list(self._threshold_row_widgets):
            if key not in active_threshold_keys:
                try:
                    self._threshold_row_widgets[key]["wrap"].destroy()
                except tk.TclError:
                    pass
                del self._threshold_row_widgets[key]

        self._bind_reward_wheel_tree(self._weights_container)
    def _sync_enabled_modules(self):
        reward_config.set_enabled_modules(self._enabled_modules())
        self._refresh_reward_panel()
        self._update_state_display()
        self._refresh_export()
        self._refresh_move_gate()

    def _refresh_reward_panel(self):
        labels = self._enabled_labels()
        self.formula_builder.set_labels(labels)
        self._refresh_weight_panel()
        self._sync_config_from_ui()

    def _collect_element_weights(self):
        out = dict(_DEFAULT_WEIGHTS)
        first_instance = {}
        for eid, idx in self._active_reward_instance_keys:
            if eid in first_instance:
                continue
            var = self._weight_instance_vars.get((eid, idx))
            if var is None:
                continue
            raw = var.get().strip()
            try:
                first_instance[eid] = float(raw) if "." in raw else int(raw)
            except ValueError:
                first_instance[eid] = _DEFAULT_WEIGHTS.get(eid, _DEFAULT_BLOCK_WEIGHT)
        out.update(first_instance)
        for eid, var in self._weight_vars.items():
            if eid in first_instance:
                continue
            raw = var.get().strip()
            try:
                out[eid] = float(raw) if "." in raw else int(raw)
            except ValueError:
                out[eid] = _DEFAULT_WEIGHTS.get(eid, _DEFAULT_BLOCK_WEIGHT)
        return out

    def _collect_thresholds(self):
        out = {}
        first_instance_by_key = {}
        for eid, idx, tk_key in self._active_threshold_instance_keys:
            var = self._threshold_instance_vars.get((eid, idx, tk_key))
            if var is None:
                continue
            try:
                val = int(var.get())
            except ValueError:
                val = reward_config.get_reward_dict().get(tk_key, 0)
            if tk_key not in first_instance_by_key:
                first_instance_by_key[tk_key] = val

        for k in THRESHOLD_LABELS:
            if k in first_instance_by_key:
                out[k] = first_instance_by_key[k]
                continue
            var = self._threshold_vars.get(k)
            if var is None:
                out[k] = reward_config.get_reward_dict().get(k, 0)
                continue
            try:
                out[k] = int(var.get())
            except ValueError:
                out[k] = reward_config.get_reward_dict().get(k, 0)
        return out

    def _collect_threshold_instances(self):
        out = {}
        for eid, idx, tk_key in self._active_threshold_instance_keys:
            var = self._threshold_instance_vars.get((eid, idx, tk_key))
            if var is None:
                continue
            try:
                val = int(var.get())
            except ValueError:
                val = reward_config.get_reward_dict().get(tk_key, 0)
            out[self._threshold_instance_id(eid, idx, tk_key)] = val
        return out

    def _collect_instance_configs(self):
        out = {}
        for eid, idx in self._active_reward_instance_keys:
            iid = self._reward_instance_id(eid, idx)
            w_var = self._weight_instance_vars.get((eid, idx))
            if w_var is None:
                continue
            raw = w_var.get().strip()
            try:
                weight = float(raw) if "." in raw else int(raw)
            except ValueError:
                weight = _DEFAULT_WEIGHTS.get(eid, _DEFAULT_BLOCK_WEIGHT)

            thresholds = {}
            tk_keys = _THRESHOLD_FOR_EID.get(eid)
            keys = tk_keys if isinstance(tk_keys, list) else ([tk_keys] if tk_keys else [])
            for tk_key in keys:
                t_var = self._threshold_instance_vars.get((eid, idx, tk_key))
                if t_var is None:
                    continue
                try:
                    thresholds[tk_key] = int(t_var.get())
                except ValueError:
                    thresholds[tk_key] = reward_config.get_reward_dict().get(tk_key, 0)
            out[iid] = {"eid": eid, "weight": weight, "thresholds": thresholds}
        return out

    def _sync_config_from_ui(self):
        weights = self._collect_element_weights()
        reward_config.sync_weights_from_elements(weights)
        thresholds = self._collect_thresholds()
        for k, v in thresholds.items():
            if k in reward_config.REWARD_KEYS:
                setattr(reward_config, k, v)
        reward_config.set_instance_configs(self._collect_instance_configs())
        reward_config.set_total_formula_student(self.formula_builder.get_expr())

    def _on_weight_edited(self):
        self._sync_config_from_ui()
        self._refresh_export()

    def _on_formula_changed(self):
        # Cập nhật panel ngay để tránh cảm giác mất khung khi xóa/thêm nhanh.
        self._refresh_weight_panel()
        self._refresh_move_gate()
        if self._formula_fx_after_id:
            try:
                self.root.after_cancel(self._formula_fx_after_id)
            except tk.TclError:
                pass
        self._formula_fx_after_id = self.root.after(200, self._apply_formula_side_effects)

    def _apply_formula_side_effects(self):
        self._formula_fx_after_id = None
        self._sync_config_from_ui()
        self._refresh_export()

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

    def _label_for_instance(self, eid, idx):
        base = self._label_for_eid(eid)
        try:
            i = int(idx)
        except (TypeError, ValueError):
            i = 1
        return "%s #%d" % (base, i)

    def _update_state_display(self):
        enabled = self._enabled_modules()
        snap = self.world.get_state_snapshot(enabled)
        n, w, e, s = snap["obs"]
        state_rows = [
            "Vị trí (%d,%d)  hướng %s" % (snap["pos"][0], snap["pos"][1], snap["heading"]),
        ]
        if "obstacle" in enabled:
            state_rows.append(
                "Tường nhìn thấy: N=%d W=%d E=%d S=%d" % (n, w, e, s)
            )
            visited = snap.get("visited_before", 0)
            state_rows.append(
                "Đã qua: %s" % ("1" if visited else "0")
            )
        if "goal" in enabled:
            state_rows.append("Trend goal: %+d" % snap["goal_trend"])
        if "checkpoint" in enabled:
            state_rows.append("Trend CP: %s" % snap["cp_trends"])
        state_rows.append("State: %d" % snap["s"])

        has_action = bool(self.world.last_action)
        parts = []
        if has_action:
            for rec in (self.world.last_instance_parts or []):
                eid = rec.get("eid")
                idx = rec.get("idx")
                if not eid:
                    continue
                val = float(rec.get("value", 0.0))
                if not val:
                    continue
                style = module_chip_style(REWARD_ELEMENTS[eid]["module"])
                parts.append((self._label_for_instance(eid, idx), style["bg"], style["fg"], val))

        self.scenario_map.set_result_display(
            state_rows=state_rows,
            has_action=has_action,
            action_name=self.world.last_action or "",
            formula=self.formula_builder.get_expr(),
            total=self.world.last_total,
            parts=parts,
        )

    def _load_from_module(self):
        d = reward_config.get_reward_dict()
        for eid, wkey in ELEMENT_WEIGHT_KEY.items():
            if eid in self._weight_vars and wkey in d:
                self._weight_vars[eid].set(str(d[wkey]))
        for k, var in self._threshold_vars.items():
            if k in d:
                var.set(str(d[k]))
        self._weight_instance_saved_values = {}
        self._threshold_instance_saved_values = {}
        self._clear_weight_panel_widgets()
        self._weight_instance_vars = {}
        self._threshold_instance_vars = {}
        self._weight_panel_sig = None
        for iid, cfg in (reward_config.get_instance_configs() or {}).items():
            if not isinstance(cfg, dict):
                continue
            if "weight" in cfg:
                self._weight_instance_saved_values[str(iid)] = cfg.get("weight")
            for tk_key, val in (cfg.get("thresholds") or {}).items():
                self._threshold_instance_saved_values["%s:%s" % (iid, tk_key)] = val
        reward_config.set_enabled_modules(self._enabled_modules())
        self.formula_builder.set_labels(self._enabled_labels())
        self.formula_builder.set_expr("")
        reward_config.set_total_formula_student("")
        self._loaded_formula_name = ""
        reward_config.set_formula_name("")

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
        snap = build_snapshot(
            self._enabled_modules(),
            self.formula_builder.get_expr(),
            weights,
            thresholds,
        )
        snap["instance_configs"] = self._collect_instance_configs()
        snap["threshold_instances"] = self._collect_threshold_instances()
        return snap

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
            reward_config.set_instance_configs(data.get("instance_configs") or {})
            try:
                import Simulation.robot.trainer as trainer
                importlib.reload(trainer)
            except Exception:
                pass

            self.apply_status.set("Đã áp dụng công thức: %s" % self._loaded_formula_name)
            self._notify_formula_applied()
            return True
        except Exception as exc:
            messagebox.showerror("Nạp công thức", "Lỗi nạp công thức: %s" % exc, parent=self.root)
            return False

    def _apply_formula_snapshot(self, data):
        from RL_lib.formula_store import migrate_formula_snapshot

        data = migrate_formula_snapshot(data)
        self._loading = True
        try:
            weights = data.get("element_weights") or {}
            for eid, var in self._weight_vars.items():
                if eid in weights:
                    var.set(str(weights[eid]))

            thresholds = data.get("thresholds") or {}
            for k, var in self._threshold_vars.items():
                if k in thresholds:
                    var.set(str(thresholds[k]))
            self._weight_instance_saved_values = {}
            self._threshold_instance_saved_values = {}
            self._clear_weight_panel_widgets()
            self._weight_instance_vars = {}
            self._threshold_instance_vars = {}
            self._weight_panel_sig = None
            for iid, cfg in (data.get("instance_configs") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                if "weight" in cfg:
                    self._weight_instance_saved_values[str(iid)] = cfg.get("weight")
                for tk_key, val in (cfg.get("thresholds") or {}).items():
                    self._threshold_instance_saved_values["%s:%s" % (iid, tk_key)] = val
            self._threshold_instance_saved_values.update(dict(data.get("threshold_instances") or {}))

            expr = data.get("total_formula") or ""
            self.formula_builder.set_labels(self._enabled_labels())
            self.formula_builder.set_expr(expr)
            self._sync_enabled_modules()
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
            reward_config.set_instance_configs(snapshot.get("instance_configs") or {})
            try:
                import Simulation.robot.trainer as trainer
                importlib.reload(trainer)
            except Exception:
                pass
            self.apply_status.set(
                "Đã lưu %s + áp dụng Train — %s"
                % (os.path.basename(json_path), save_name)
            )
            self._notify_formula_applied()
        except Exception as exc:
            self.apply_status.set("Lỗi lưu: %s" % exc)
            messagebox.showerror("Lưu công thức", str(exc), parent=self.root)

    def _reset_defaults(self):
        for eid, var in self._weight_vars.items():
            var.set(str(_DEFAULT_WEIGHTS.get(eid, _DEFAULT_BLOCK_WEIGHT)))
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
        self._weight_instance_saved_values = {}
        self._clear_weight_panel_widgets()
        self._weight_instance_vars = {}
        self._active_reward_instance_keys = []
        self._threshold_instance_saved_values = {}
        self._threshold_instance_vars = {}
        self._active_threshold_instance_keys = []
        self._weight_panel_sig = None
        self.formula_builder.set_tokens(default_total_formula(self._enabled_modules()))
        reward_config.set_total_formula_student("")
        self.world.reset_scenario()
        self.scenario_map.redraw()
        self._sync_enabled_modules()
        self._loaded_formula_name = ""
        reward_config.set_formula_name("")

    def refresh_ui_scale(self):
        try:
            self._main_layout.pack_configure(padx=px(6), pady=px(6))
        except (tk.TclError, AttributeError):
            pass
        for w, sz, wt in self._scaled_font_widgets:
            try:
                w.configure(font=font(sz, weight=wt))
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
        for tr in self._threshold_instance_rows + self._weight_instance_rows:
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
