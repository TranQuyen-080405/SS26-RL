"""
Scale UI theo kích thước cửa sổ / màn hình — thiết kế gốc 1200×720 (cửa sổ), 1920×1080 (màn).

Gọi init(root) sau Tk(), attach_window_scaling(root) sau khi dựng UI.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

BASE_SCREEN_W = 1920
BASE_SCREEN_H = 1080
DESIGN_WIN_W = 1200
DESIGN_WIN_H = 720
# Thu nhỏ chữ/padding/nút so với thiết kế gốc; vẫn co giãn theo cửa sổ
UI_SIZE_BIAS = 0.80

_scale = 1.0
_initialized = False
_screen_w = 1920
_screen_h = 1080
_root_ref: tk.Misc | None = None
_resize_after_id: str | None = None
_on_scale_change = None
_scale_listeners: list = []


def scale() -> float:
    return _scale


def px(n: float) -> int:
    return max(1, int(round(float(n) * _scale)))


def font(size: int, family: str = "", weight: str = "normal"):
    sz = max(7, int(round(size * _scale)))
    if family:
        return (family, sz, weight) if weight != "normal" else (family, sz)
    return ("", sz, weight) if weight != "normal" else ("", sz)


def entry_width(chars: int) -> int:
    return max(3, int(round(chars * _scale)))


def text_lines(lines: int) -> int:
    return max(3, int(round(lines * _scale)))


def wrap_px(n: int) -> int:
    return px(n)


def screen_size() -> tuple[int, int]:
    return _screen_w, _screen_h


def is_small_screen() -> bool:
    """Khung app hẹp — dùng cho layout phụ (không cố định scale)."""
    if _root_ref is not None:
        try:
            _root_ref.update_idletasks()
            if _root_ref.winfo_width() > 100:
                return _root_ref.winfo_width() < px(1100)
        except tk.TclError:
            pass
    return _screen_w < 1440 or _screen_h < 800


def _detect_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _clamp_scale(raw: float) -> float:
    return max(0.50, min(1.50, raw * UI_SIZE_BIAS))


def _scale_from_dims(width: int, height: int) -> float:
    """Hệ số từ kích thước khung thực tế so với thiết kế 1200×720."""
    if width < 120 or height < 120:
        return _scale
    sx = width / DESIGN_WIN_W
    sy = height / DESIGN_WIN_H
    return _clamp_scale(min(sx, sy))


def _scale_from_screen(sw: int, sh: int) -> float:
    sx = sw / BASE_SCREEN_W
    sy = sh / BASE_SCREEN_H
    return _clamp_scale(min(sx, sy))


def add_scale_listener(callback) -> None:
    """Đăng ký hàm gọi mỗi lần cửa sổ đổi kích thước."""
    if callback not in _scale_listeners:
        _scale_listeners.append(callback)


def _notify_scale_listeners() -> None:
    if _on_scale_change:
        try:
            _on_scale_change()
        except Exception:
            pass
    for fn in list(_scale_listeners):
        try:
            fn()
        except Exception:
            pass


def _read_screen(root: tk.Misc) -> tuple[int, int]:
    root.update_idletasks()
    return max(800, root.winfo_screenwidth()), max(600, root.winfo_screenheight())


def btn_padding() -> tuple[int, int]:
    """Padding nút ttk — compact."""
    return (px(3), px(1))


def _apply_ttk_defaults(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    pad = btn_padding()
    f = font(10)
    f_btn = font(10)
    fb = font(10, weight="bold")
    for name in (
        ".",
        "TLabel",
        "TCheckbutton",
        "TRadiobutton",
        "TEntry",
        "TCombobox",
        "TSpinbox",
        "TLabelframe.Label",
    ):
        try:
            style.configure(name, font=f)
        except tk.TclError:
            pass
    try:
        style.configure("TButton", font=f_btn, padding=pad)
        style.configure("TLabelframe", padding=px(6))
        style.configure("Treeview", rowheight=px(28), font=font(9, family="Segoe UI"))
        style.configure("Treeview.Heading", font=fb, padding=(px(5), px(3)))
        style.configure("Train.Treeview", rowheight=px(28), font=font(9, family="Segoe UI"))
        style.configure("Train.Treeview.Heading", font=fb, padding=(px(5), px(3)))
    except tk.TclError:
        pass


def set_scale(new_scale: float, root: tk.Misc | None = None) -> bool:
    """Đặt scale mới và refresh style ttk. Trả True nếu đổi đáng kể."""
    global _scale
    new_scale = max(0.50, min(1.50, float(new_scale)))
    if abs(new_scale - _scale) < 0.012:
        return False
    _scale = new_scale
    r = root or _root_ref
    if r is not None:
        _apply_ttk_defaults(r)
    return True


def update_scale_from_window(root: tk.Misc | None = None) -> bool:
    """Cập nhật scale từ kích thước cửa sổ hiện tại."""
    r = root or _root_ref
    if r is None:
        return False
    r.update_idletasks()
    w, h = r.winfo_width(), r.winfo_height()
    if w < 200 or h < 200:
        return set_scale(_scale_from_screen(_screen_w, _screen_h), r)
    return set_scale(_scale_from_dims(w, h), r)


def init(root: tk.Misc) -> float:
    global _scale, _initialized, _screen_w, _screen_h, _root_ref
    _detect_dpi_awareness()
    _root_ref = root
    _screen_w, _screen_h = _read_screen(root)
    _scale = _scale_from_screen(_screen_w, _screen_h)
    _apply_ttk_defaults(root)
    _initialized = True
    return _scale


def configure_window(
    root: tk.Misc,
    *,
    width: int = DESIGN_WIN_W,
    height: int = DESIGN_WIN_H,
    min_width: int = 800,
    min_height: int = 500,
    screen_frac: float = 0.90,
) -> None:
    """Cửa sổ tỷ lệ theo màn hình — màn lớn thì app lớn, màn nhỏ thì app nhỏ."""
    if not _initialized:
        init(root)
    root.update_idletasks()
    sw, sh = _screen_w, _screen_h
    # Tỷ lệ thiết kế × màn hình (không kẹt 1200px trên màn 2K/4K)
    w = int(width * sw / BASE_SCREEN_W)
    h = int(height * sh / BASE_SCREEN_H)
    w = min(w, int(sw * screen_frac), sw - 8)
    h = min(h, int(sh * screen_frac), sh - 36)
    w = max(int(min_width * sw / BASE_SCREEN_W), w)
    h = max(int(min_height * sh / BASE_SCREEN_H), h)
    mw = max(int(480 * sw / BASE_SCREEN_W), min(int(sw * 0.55), w))
    mh = max(int(400 * sh / BASE_SCREEN_H), min(int(sh * 0.55), h))
    root.minsize(mw, mh)
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2)
    root.geometry("%dx%d+%d+%d" % (w, h, x, y))
    update_scale_from_window(root)


def attach_window_scaling(root: tk.Misc, on_change=None) -> None:
    """Theo dõi resize cửa sổ — scale chữ/UI theo khung."""
    global _root_ref, _on_scale_change
    _root_ref = root
    _on_scale_change = on_change

    def _schedule(event=None):
        global _resize_after_id
        if event is not None and event.widget != root:
            return
        if _resize_after_id is not None:
            try:
                root.after_cancel(_resize_after_id)
            except tk.TclError:
                pass
        _resize_after_id = root.after(150, _apply)

    def _apply():
        global _resize_after_id
        _resize_after_id = None
        update_scale_from_window(root)
        _notify_scale_listeners()

    root.bind("<Configure>", _schedule, add="+")
    root.after_idle(_apply)


# --- Map canvas (ô co theo khung map_layout, base theo scale hiện tại) ---

def cell_min() -> int:
    return max(8, px(14))


def cell_max() -> int:
    return px(100)


def canvas_pad() -> int:
    return max(4, px(10))


def lab_cell() -> int:
    return px(35)


def lab_cell_min() -> int:
    return max(10, px(14))


def lab_margin() -> int:
    return max(4, px(8))


def lab_max_canvas_w() -> int:
    return px(450)
