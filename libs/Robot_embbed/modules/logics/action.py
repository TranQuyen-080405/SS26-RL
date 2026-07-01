"""
Action robot thật — RL policy + xBot hardware.
Hành vi phần cứng lấy từ code mẫu robotcon_xbot:
  forward  = foward_fix() + follow_line_until(400ms)
  rotate   = turn_angle(80) + fix_line + sleep(0.5)
Giữa mỗi action có gap 0.2s.
"""
import time

from line_array import line_array
from ultrasonic import ultrasonic
from robot import robot

from modules.logics.grid import neighbor_xy
from modules.logics.robot_state import (
    update_direction, update_position,
    snapshot_dist_before_move, inject_distances_from_map,
    compute_trends_after_move, mark_moved,
    build_encoded_state, perceive_edge,
    update_rotate_streak, update_straight_streak, clear_move_trends,
)
from modules.logics.policy_io import get_policy_for_state
from modules.logics.robot_map import can_move
from modules.logics.robotcon_xbot import follow_line_until_cross

# Cấu hình
_LP    = 0     # line array port
_UP    = 1     # ultrasonic port
_SPD   = 30    # tốc độ bám line
_TURN  = 80    # góc xoay (degree)
_GAP   = 200   # delay giữa các action (ms)
_OBS   = 8     # khoảng cách phát hiện vật cản (cm)


def _log(msg):
    """Gửi log qua Bluetooth BLE lên PC và in ra Serial."""
    try:
        from modules.server.ble_monitor import publish_log
        publish_log(msg)
    except Exception:
        pass
    print(msg)


def _is_stopped():
    """Kiểm tra tín hiệu Stop từ PC."""
    try:
        from modules.server.ble_monitor import is_stopped
        return is_stopped()
    except Exception:
        return False


def _read_obstacle():
    """Đọc ultrasonic. True nếu vật cản < _OBS cm."""
    try:
        time.sleep_ms(30)
        d = ultrasonic.distance_cm(_UP)
    except Exception:
        return False
    if d >= 200:
        return False
    return d < _OBS


def _finish(bot, res):
    """Cập nhật streak counters và trả kết quả."""
    update_rotate_streak(bot, res)
    update_straight_streak(bot, res)
    return res


def _collision(bot):
    """Trả kết quả va chạm."""
    _log("SW: Collision registered")
    clear_move_trends(bot)
    return _finish(bot, {"success": False, "moved": False, "collision": True})


# ================================================================
# HW: Di chuyển thẳng — dùng follow_line_until_cross
#   1. Thoát node hiện tại (chờ tới khi KHÔNG còn (1,1,1,1))
#   2. Bám line tới node kế (phát hiện (1,1,1,1) 4 lần liên tiếp)
#   3. Chạy thêm 0.1s rồi dừng (ổn định vị trí trên node)
# ================================================================

def _forward_to_node():
    """
    Bám line từ node hiện tại tới node kế tiếp.
    Dùng follow_line_until_cross — robust hơn foward_fix:
      - Tự exit node hiện tại (status=1)
      - Follow line rồi detect node mới bằng 4 lần (1,1,1,1) (status=2)
      - Dừng đúng tại node mới
    Returns True nếu tới node, False nếu bị stop/va chạm.
    """
    _log("HW: Forward — follow_line_until_cross tới node kế")

    if _is_stopped():
        robot.stop()
        return False

    follow_line_until_cross(_SPD, _LP, 20000)
    _log("HW: Node kế tiếp reached")
    return True


# ================================================================
# HW: Căn chỉnh line sau xoay — lấy từ fix_line_right/left()
# ================================================================

def _fix_line_right():
    """Micro-adjust sau xoay phải tới khi 2 sensor giữa thấy đen (0,1,1,0)."""
    _log("HW: Căn chỉnh line sau xoay phải")
    while True:
        s = line_array.read(_LP)
        if s == (0, 1, 1, 0):
            break
        elif s in ((1, 0, 0, 0), (1, 1, 0, 0), (0, 1, 0, 0)):
            robot.turn_left_angle(3)
        elif s == (0, 0, 0, 0):
            robot.turn_left_angle(5)
        elif s in ((0, 0, 0, 1), (0, 0, 1, 1), (0, 0, 1, 0)):
            robot.turn_right_angle(4)


def _fix_line_left():
    """Micro-adjust sau xoay trái tới khi 2 sensor giữa thấy đen (0,1,1,0)."""
    _log("HW: Căn chỉnh line sau xoay trái")
    while True:
        s = line_array.read(_LP)
        if s == (0, 1, 1, 0):
            break
        elif s in ((1, 0, 0, 0), (1, 1, 0, 0), (0, 1, 0, 0)):
            robot.turn_left_angle(4)
        elif s == (0, 0, 0, 0):
            robot.turn_right_angle(5)
        elif s in ((0, 0, 0, 1), (0, 0, 1, 1), (0, 0, 1, 0)):
            robot.turn_right_angle(3)


# ================================================================
# SW: Cập nhật state sau forward
# ================================================================

def _commit_forward(bot):
    """Đã tới node mới → cập nhật x,y, dist, trend, checkpoint."""
    _log("SW: Commit forward — tính tọa độ mới")
    snapshot_dist_before_move(bot)
    nx, ny = neighbor_xy(bot["x"], bot["y"], bot["direct"])
    update_position(bot, nx, ny)
    inject_distances_from_map(bot)
    compute_trends_after_move(bot)
    _log("SW: Vị trí mới (%d,%d)" % (bot["x"], bot["y"]))
    # Đánh dấu checkpoint đã đi qua
    for i, (cx, cy) in enumerate(bot["robot_map"].get("checkpoints") or []):
        if bot["x"] == cx and bot["y"] == cy:
            vis = bot.get("cp_visited") or []
            if i < len(vis):
                vis[i] = True
                _log("SW: Checkpoint %d (%d,%d) visited" % (i, cx, cy))
    mark_moved(bot)


# ================================================================
# Các action RL — kết hợp HW + SW
# ================================================================

def forward_hw(bot):
    """Tiến 1 node: check map → ultrasonic → follow line → commit."""
    _log("HW: === FORWARD ===")
    if not can_move(bot["robot_map"], bot["x"], bot["y"], bot["direct"]):
        _log("SW: Hướng %s bị chặn trong bộ nhớ map" % bot["direct"])
        return _collision(bot)

    if _read_obstacle():
        _log("HW: Ultrasonic phát hiện vật cản")
        perceive_edge(bot, True)
        _log("SW: Cập nhật tường hướng %s" % bot["direct"])
        return _collision(bot)

    if not _forward_to_node():
        _log("HW: Forward thất bại")
        perceive_edge(bot, True)
        return _collision(bot)

    _commit_forward(bot)
    _log("HW: Forward thành công → (%d,%d)" % (bot["x"], bot["y"]))
    return _finish(bot, {"success": True, "moved": True, "collision": False})


def rotate_left_hw(bot):
    """Xoay trái: motor turn → fix line → cập nhật hướng."""
    _log("HW: === ROTATE LEFT ===")
    robot.turn_left_angle(_TURN)
    _fix_line_left()
    time.sleep_ms(500)
    # SW: cập nhật hướng
    update_direction(bot, "left")
    clear_move_trends(bot)
    _log("SW: Hướng mới = %s" % bot["direct"])
    return _finish(bot, {"success": True, "moved": False, "collision": False})


def rotate_right_hw(bot):
    """Xoay phải: motor turn → fix line → cập nhật hướng."""
    _log("HW: === ROTATE RIGHT ===")
    robot.turn_right_angle(_TURN)
    _fix_line_right()
    time.sleep_ms(500)
    # SW: cập nhật hướng
    update_direction(bot, "right")
    clear_move_trends(bot)
    _log("SW: Hướng mới = %s" % bot["direct"])
    return _finish(bot, {"success": True, "moved": False, "collision": False})


def execute_action(bot, action):
    """Thực thi 1 action (blocking — chờ xong mới return)."""
    if action == "forward":
        return forward_hw(bot)
    if action == "rotate left":
        return rotate_left_hw(bot)
    if action == "rotate right":
        return rotate_right_hw(bot)
    return _finish(bot, {"success": False, "moved": False, "collision": False})


# ================================================================
# Vòng lặp RL: 1 bước infer
# ================================================================

def run_policy_step(bot):
    """
    1 bước infer:
      1. Quét ultrasonic → cập nhật tường
      2. Encode state → query policy → chọn action
      3. Execute action (blocking)
      4. Gap 0.2s giữa các bước
    """
    _log("--- run_policy_step ---")

    # 1. HW: quét ultrasonic trước mặt
    obs = _read_obstacle()
    _log("HW: Ultrasonic = %s" % ("vật cản" if obs else "trống"))
    perceive_edge(bot, obs)
    if obs:
        _log("SW: Tường hướng %s ghi nhận" % bot["direct"])

    # 2. SW: encode state → chọn action từ Q-table
    s = build_encoded_state(bot)
    _log("SW: State=%d" % s)
    name = get_policy_for_state(s)
    _log("SW: Policy → %s" % name)

    # 3. Execute action (blocking)
    result = execute_action(bot, name)
    _log("SW: Kết quả: success=%s moved=%s collision=%s" % (
        result.get("success"), result.get("moved"), result.get("collision")))

    # 4. Gap 0.2s — chia nhỏ để có thể dừng ngay
    for _ in range(4):
        if _is_stopped():
            break
        time.sleep_ms(50)

    return name, result
