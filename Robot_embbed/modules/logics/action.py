import time
from readSensor import read_line
from policy import get_action 
from robot import robot
from motor import motor
from policy import get_policy

# Hệ số tốc bánh: [trái, phải] theo move_mode — dùng với steer_side trong _set_wheels
# move_mode 0: thẳng | 1: rẽ nhẹ | 2: rẽ vừa | 3: rẽ gắt
_WHEEL_FACTORS = [
    [1.0, 1.0],
    [0.7, 1.0],
    [0.0, 1.0],
    [-0.5, 0.5],
]

_MIN_WHEEL_SPEED = 30

_last_move_mode = -1   # -1: chưa xác định | 0: thẳng | 1: rẽ nhẹ | 2: rẽ vừa | 3: rẽ gắt
_steer_side = 0        # 0: chỉnh về trái | 1: chỉnh về phải


def _clamp_speed(v):
    v = int(v)
    if v < 0 and v > -_MIN_WHEEL_SPEED:
        return -_MIN_WHEEL_SPEED
    if 0 < v < _MIN_WHEEL_SPEED:
        return _MIN_WHEEL_SPEED
    return v


def _set_wheels(move_mode, steer_side, speed):
    factors = _WHEEL_FACTORS[move_mode]
    left = _clamp_speed(speed * factors[steer_side])
    right = _clamp_speed(speed * factors[1 - steer_side])
    robot.set_wheel_speed(left, right)


def _brake():
    motor._pin(11, True)
    motor._pin(12, True)
    motor._pin(13, True)
    motor._pin(14, True)
    time.sleep_ms(50)


def _turn_90(mode):
    match mode:
        case "left":
            robot.turn_left_angle(90)
        case "right":
            robot.turn_right_angle(90)
        case _:
            print("Invalid mode in _turn_90")


def _follow_line(speed=25, port=0, backward=True):
    global _last_move_mode, _steer_side

    action = read_line(port)

    if action == "lost":
        if backward:
            robot.backward(int(speed * 0.7))

    elif action == "node":
        robot.set_wheel_speed(int(speed * 0.5), int(speed * 0.5))

    elif action == "forward":
        if _last_move_mode == 0:
            robot.set_wheel_speed(speed, speed)
        else:
            _last_move_mode = 0
            robot.set_wheel_speed(int(speed * 0.7), int(speed * 0.7))

    elif action == "right":
        _last_move_mode = 2
        _steer_side = 0
        _set_wheels(_last_move_mode, _steer_side, speed)

    elif action == "left":
        _last_move_mode = 2
        _steer_side = 1
        _set_wheels(_last_move_mode, _steer_side, speed)

    else:
        robot.set_wheel_speed(int(speed * 0.5), int(speed * 0.5))


def forward_action():
    _follow_line(speed=25, port=0, backward=False)

def rotate_left(mode="left"):
    _turn_90(mode)

def rotate_right(mode="right"):
    _turn_90(mode)

def Action(encoded_state, Q = []):
    robot.forward(25,0.5)
    time.sleep_ms(100)

    while True:
        match get_policy(encoded_state, Q):
            case "forward":
                forward_action()
                break
            case "rotate left":
                rotate_left()
                #cập nhật state ở đây
            case "rotate right":
                rotate_right()
                #cập nhật state ở đây
        time.sleep_ms(5000)