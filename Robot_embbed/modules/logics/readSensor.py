import time
from line_array import line_array
from ultrasonic import ultrasonic

# Khai báo ngoài vòng lặp — tái sử dụng buffer, tránh tạo list mới mỗi vòng
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
    time.sleep_ms(50)
    dist = ultrasonic.distance_cm(port)
    if dist >= 200:          # out-of-range
        return None
    elif dist < 8:
        return 1


def read_line(port=0):
    # S1 S2 S3 S4 — 0: nền trắng, 1: line đen
    match read_sensors(port):

        case (0, 0, 0, 0):
            # Mất line → lùi chậm (speed*0.7) để tìm lại line
            return "lost"

        case (1, 1, 1, 1):
            # dừng - cập nhật state
            return "node"

        case (0, 1, 1, 0):
            # Giữa line (S2,S3 đều thấy đen) → tiến thẳng
            return "forward"

        case (1, 1, 0, 0) | (1, 0, 0, 0):
            # Lệch qua phải → rẽ trái
            return "right"

        case (0, 0, 1, 1) | (0, 0, 0, 1):
            # Lệch qua trái → rẽ phải
            return "left"

        case _:
            # Pattern chưa map — giữ tốc thấp hoặc dừng, log để bổ sung case
            return "unknown"
