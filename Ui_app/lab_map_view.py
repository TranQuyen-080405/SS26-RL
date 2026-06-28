"""
Map 3×3 Learn Lab — preview state tiếp theo + animation chạy thử.
"""

import tkinter as tk
from tkinter import ttk

_DIR_ARROW = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
_TREND_COLOR = {-1: "#f38ba8", 0: "#45475a", 1: "#a6e3a1"}
_WALL_COLOR = "#f38ba8"
_ROBOT_FILL = "#cba6f7"
_ROBOT_OUTLINE = "#cdd6f4"


class LabStateCanvas:
    """Một map 3×3: ghost state tiếp theo → robot nhảy vào + điểm reward."""

    CELL = 56
    MARGIN = 28

    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="State tiếp theo — test trực quan", padding=8)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.mode_var = tk.StringVar(value="Chỉnh state bên trái → bấm Chạy thử")
        ttk.Label(
            self.frame,
            textvariable=self.mode_var,
            font=("", 10, "bold"),
            anchor=tk.CENTER,
        ).pack(fill=tk.X, pady=(0, 6))

        self.canvas = tk.Canvas(self.frame, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack()
        self.score_var = tk.StringVar(value="")
        self.score_label = ttk.Label(
            self.frame, textvariable=self.score_var, font=("", 14, "bold"), anchor=tk.CENTER
        )
        self.score_label.pack(fill=tk.X, pady=(8, 4))

        self.detail_var = tk.StringVar(value="")
        ttk.Label(
            self.frame, textvariable=self.detail_var, justify=tk.LEFT, wraplength=340, anchor=tk.W
        ).pack(fill=tk.X)

        self._preview = True
        self._anim_id = None
        self._pulse = 0

    def show_preview(
        self,
        obs_nwes,
        goal_trend,
        cp_trends,
        heading,
        action,
        s=None,
        policy_action=None,
    ):
        self._preview = True
        self._cancel_anim()
        self.mode_var.set("STATE TIẾP THEO — sau khi robot thực hiện action")
        self.score_var.set("")
        self.detail_var.set(self._build_detail(obs_nwes, goal_trend, cp_trends, heading, action, s, policy_action))
        self._draw_grid(obs_nwes, goal_trend, cp_trends, heading, action, active=False, highlight_next=True)

    def run_test(
        self,
        obs_nwes,
        goal_trend,
        cp_trends,
        heading,
        action,
        total,
        parts,
        s=None,
    ):
        self._preview = False
        self._cancel_anim()
        self.mode_var.set("Robot đã vào state tiếp theo")
        sign = "+" if total >= 0 else ""
        self.score_var.set("%s%.1f điểm" % (sign, total))
        self.detail_var.set(self._format_breakdown(parts, action, s))
        self._draw_grid(obs_nwes, goal_trend, cp_trends, heading, action, active=True, highlight_next=False)
        self._pulse = 0
        self._animate_pulse(obs_nwes, goal_trend, cp_trends, heading, action, total, parts, s)

    def _cancel_anim(self):
        if self._anim_id:
            self.canvas.after_cancel(self._anim_id)
            self._anim_id = None

    def _animate_pulse(self, obs, gt, cps, heading, action, total, parts, s):
        if self._pulse >= 6:
            self._draw_grid(obs, gt, cps, heading, action, active=True, highlight_next=False)
            return
        self._pulse += 1
        glow = "#a6e3a1" if total >= 0 else "#f38ba8"
        if self._pulse % 2:
            self._draw_grid(
                obs, gt, cps, heading, action, active=True, highlight_next=False, border_color=glow
            )
        else:
            self._draw_grid(obs, gt, cps, heading, action, active=True, highlight_next=False)
        self._anim_id = self.canvas.after(120, lambda: self._animate_pulse(obs, gt, cps, heading, action, total, parts, s))

    def _grid_size(self):
        cell = self.CELL
        m = self.MARGIN
        grid = 3
        return grid, cell, m, grid * cell + 2 * m

    def _draw_grid(
        self,
        obs_nwes,
        goal_trend,
        cp_trends,
        heading,
        action,
        *,
        active,
        highlight_next,
        border_color="#f9e2af",
    ):
        c = self.canvas
        c.delete("all")
        grid, cell, m, size = self._grid_size()
        c.config(width=size, height=size + 20, scrollregion=(0, 0, size, size + 20))

        n, w, e, s = (int(x) for x in obs_nwes)
        walls = {"N": n, "W": w, "E": e, "S": s}

        if highlight_next:
            c.create_rectangle(4, 4, size - 4, size - 4, outline=border_color, width=3, dash=(6, 4))
            c.create_text(
                size // 2, 12, text="STATE TIẾP THEO", fill=border_color, font=("", 9, "bold")
            )

        cx, cy = m + cell + cell // 2, m + cell + cell // 2

        for gy in range(grid):
            for gx in range(grid):
                px = m + gx * cell
                py = m + (grid - 1 - gy) * cell
                fill = "#313244"
                if gx == 1 and gy == 1:
                    fill = "#585b70" if active else "#45475a"
                elif gx == 1 and gy == 2:
                    fill = _TREND_COLOR.get(goal_trend, "#313244")
                c.create_rectangle(px, py, px + cell, py + cell, fill=fill, outline="#6c7086", width=1)

        self._draw_dir_labels(c, cx, cy, cell)
        self._draw_walls(c, cx, cy, cell, walls, active)
        self._draw_action_hint(c, cx, cy, cell, action, walls, active)
        self._draw_robot(c, cx, cy, cell, heading, active, action)
        self._draw_trend_badges(c, m, cell, goal_trend, cp_trends)

    def _draw_dir_labels(self, c, cx, cy, cell):
        half = cell // 2 + 8
        for d, (dx, dy) in _DIR_ARROW.items():
            c.create_text(
                cx + dx * half, cy + dy * half, text=d, fill="#89b4fa", font=("", 10, "bold")
            )

    def _draw_walls(self, c, cx, cy, cell, walls, active):
        hw = cell // 2 - 4
        thick = 8 if active else 6
        for d, blocked in walls.items():
            if not blocked:
                continue
            if d == "N":
                c.create_rectangle(
                    cx - hw, cy - hw - 6, cx + hw, cy - hw + thick - 6, fill=_WALL_COLOR, outline=""
                )
            elif d == "S":
                c.create_rectangle(
                    cx - hw, cy + hw - thick + 6, cx + hw, cy + hw + 6, fill=_WALL_COLOR, outline=""
                )
            elif d == "W":
                c.create_rectangle(
                    cx - hw - 6, cy - hw, cx - hw + thick - 6, cy + hw, fill=_WALL_COLOR, outline=""
                )
            elif d == "E":
                c.create_rectangle(
                    cx + hw - thick + 6, cy - hw, cx + hw + 6, cy + hw, fill=_WALL_COLOR, outline=""
                )

    def _draw_action_hint(self, c, cx, cy, cell, action, walls, active):
        color = "#89b4fa" if active else "#6c7086"
        if action == "forward":
            if walls.get("N"):
                c.create_text(cx, cy - cell - 6, text="forward → va tường!", fill="#f38ba8", font=("", 9, "bold"))
            else:
                c.create_line(
                    cx, cy - cell // 2 - 4, cx, cy - cell - 10,
                    fill=color, width=3, arrow=tk.LAST, arrowshape=(10, 12, 5),
                )
                c.create_text(cx + 28, cy - cell // 2 - 8, text="forward", fill=color, font=("", 8))
        elif action == "rotate left":
            c.create_arc(
                cx - 18, cy - 18, cx + 18, cy + 18, start=90, extent=90,
                style=tk.ARC, outline=color, width=2,
            )
            c.create_text(cx + cell // 2 + 16, cy - 8, text="↺ trái", fill=color, font=("", 8))
        elif action == "rotate right":
            c.create_arc(
                cx - 18, cy - 18, cx + 18, cy + 18, start=0, extent=-90,
                style=tk.ARC, outline=color, width=2,
            )
            c.create_text(cx + cell // 2 + 16, cy - 8, text="↻ phải", fill=color, font=("", 8))

    def _draw_robot(self, c, cx, cy, cell, heading, active, action):
        r = cell // 4
        fill = _ROBOT_FILL if active else "#7f849c"
        outline = _ROBOT_OUTLINE if active else "#585b70"
        width = 3 if active else 1
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=width)
        dx, dy = _DIR_ARROW.get(heading, (0, -1))
        ax, ay = cx + dx * (r + 8), cy + dy * (r + 8)
        c.create_line(cx, cy, ax, ay, fill="#1e1e2e", width=3, arrow=tk.LAST, arrowshape=(8, 10, 4))
        if not active:
            c.create_text(cx, cy + r + 14, text="(ghost)", fill="#6c7086", font=("", 7))

    def _draw_trend_badges(self, c, m, cell, goal_trend, cp_trends):
        bx = m + 3 * cell + 4
        by = m + cell // 2
        if goal_trend != 0:
            lbl = "Goal %s" % ("+" if goal_trend > 0 else "−")
            c.create_text(bx, by, text=lbl, fill=_TREND_COLOR[goal_trend], font=("", 8, "bold"), anchor=tk.W)
        for i, t in enumerate(cp_trends[:3]):
            if t:
                c.create_text(
                    bx, by + 16 * (i + 1),
                    text="CP%d %s" % (i + 1, "+" if t > 0 else "−"),
                    fill=_TREND_COLOR[t], font=("", 8), anchor=tk.W,
                )

    def _build_detail(self, obs, gt, cps, heading, action, s, policy_action):
        n, w, e, s = obs
        lines = [
            "Action: %s  |  heading sau: %s" % (action, heading),
            "Obstacle N=%d W=%d E=%d S=%d" % (n, w, e, s),
            "Trend goal=%d  CP=%s" % (gt, cps),
        ]
        if s is not None:
            lines.append("s = %d" % s)
        if policy_action:
            lines.append("Policy gợi ý: %s" % policy_action)
        lines.append("→ Bấm Chạy thử: robot vào state này và tính điểm")
        return "\n".join(lines)

    def _format_breakdown(self, parts, action, s):
        lines = ["Action: %s" % action]
        if s is not None:
            lines.append("s = %d" % s)
        for name, val in parts.items():
            if val:
                lines.append("  %-16s %+.1f" % (name, val))
        return "\n".join(lines)
