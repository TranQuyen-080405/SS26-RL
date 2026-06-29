"""Cấu hình map deploy — sửa file này; PC Robot Monitor đọc cùng bản."""

MAP_W = 10
MAP_H = 10
START = (0, 0)
GOAL = (MAP_W - 1, MAP_H - 1)
CHECKPOINTS = []
# Tường nội bộ [{"x", "y", "dir"} hoặc [x, y, dir]] — mép map tự thêm khi init
WALLS = []
