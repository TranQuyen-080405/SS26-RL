"""Co ô map vừa khung — phóng tối đa trong khung, căn giữa, không vùng đen thừa."""

from __future__ import annotations

from Ui_app.ui_scale import canvas_pad, cell_max, px, clamp_canvas_dim


def map_cell_floor() -> int:
    return max(8, px(12))


def fit_grid_layout(
    grid_w: int,
    grid_h: int,
    avail_w: int,
    avail_h: int,
    *,
    margin: int | None = None,
    max_cell: int | None = None,
):
    """
    Ô map lớn nhất vừa khung avail_w × avail_h; map căn giữa trên canvas full khung.
    Trả (cell, offset_x, offset_y, canvas_w, canvas_h).
    """
    _ = margin  # giữ tham số tương thích; lề tính bằng căn giữa
    cap = max_cell if max_cell is not None else cell_max()
    floor = map_cell_floor()
    cw = clamp_canvas_dim(max(1, int(avail_w)))
    ch = clamp_canvas_dim(max(1, int(avail_h)))
    gw = max(1, int(grid_w))
    gh = max(1, int(grid_h))
    by_w = cw // gw
    by_h = ch // gh
    cell = max(floor, min(cap, by_w, by_h))
    map_w = gw * cell
    map_h = gh * cell
    ox = max(0, (cw - map_w) // 2)
    oy = max(0, (ch - map_h) // 2)
    return cell, ox, oy, cw, ch


def fit_grid_layout_tight(
    grid_w: int,
    grid_h: int,
    avail_w: int,
    avail_h: int | None = None,
    *,
    margin: int | None = None,
    max_cell: int | None = None,
):
    """Canvas = đúng kích thước lưới. avail_h mặc định theo tỷ lệ lưới × avail_w."""
    gw = max(1, int(grid_w))
    gh = max(1, int(grid_h))
    aw = max(1, int(avail_w))
    if avail_h is None:
        ah = max(map_cell_floor() * gh, aw * gh // gw)
    else:
        ah = max(1, int(avail_h))
    cell, _, _, _, _ = fit_grid_layout(
        gw, gh, aw, ah, margin=margin, max_cell=max_cell
    )
    map_w = gw * cell
    map_h = gh * cell
    return cell, 0, 0, clamp_canvas_dim(map_w), clamp_canvas_dim(map_h)


def avail_width_from_wrap(wrap, *, min_w: int = 120) -> int:
    """Chiều rộng khung — dùng cho layout tight (không đọc height wrap)."""
    wrap.update_idletasks()
    try:
        w = wrap.winfo_width()
    except tk.TclError:
        w = 0
    if w <= 1 or w > 4096:
        w = min_w
    return clamp_canvas_dim(max(px(min_w), w))


def avail_from_wrap(wrap, *, min_w: int = 120, min_h: int = 80) -> tuple[int, int]:
    wrap.update_idletasks()
    try:
        w = wrap.winfo_width()
        h = wrap.winfo_height()
    except tk.TclError:
        w, h = 0, 0
    if w <= 1 or w > 4096:
        w = min_w
    if h <= 1 or h > 4096:
        h = min_h
    return clamp_canvas_dim(max(px(min_w), w)), clamp_canvas_dim(max(px(min_h), h))


def apply_fixed_canvas(canvas, canvas_w: int, canvas_h: int) -> None:
    canvas_w = clamp_canvas_dim(canvas_w)
    canvas_h = clamp_canvas_dim(canvas_h)
    canvas.config(width=canvas_w, height=canvas_h, scrollregion=(0, 0, canvas_w, canvas_h))
