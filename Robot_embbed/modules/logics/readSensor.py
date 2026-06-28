import time
from ultrasonic import ultrasonic
from line_array import line_array
_line_sensors = [0, 0, 0, 0]


def read_sensors(port=0):
    """Đọc S1..S4 vào buffer cố định, trả về cùng list (không cấp phát mới)."""
    raw = line_array.read(port)
    _line_sensors[0] = raw[0]
    _line_sensors[1] = raw[1]
    _line_sensors[2] = raw[2]
    _line_sensors[3] = raw[3]
    return _line_sensors


def read_obstacle(port=1):
    try:
        time.sleep_ms(30)
        dist = ultrasonic.distance_cm(port)
    except Exception:
        return None
    if dist >= 200:
        return None
    if dist < 8:
        return 1
    return None


def read_line(port=0):
    # S1 S2 S3 S4 — 0: nền trắng, 1: line đen (if/elif — tương thích MicroPython)
    s = tuple(read_sensors(port))
    if s == (0, 0, 0, 0):
        return "lost"
    if s == (1, 1, 1, 1):
        return "node"
    if s == (0, 1, 1, 0):
        return "forward"
    if s in ((1, 1, 0, 0), (1, 0, 0, 0)):
        return "right"
    if s in ((0, 0, 1, 1), (0, 0, 0, 1)):
        return "left"
    return "unknown"
