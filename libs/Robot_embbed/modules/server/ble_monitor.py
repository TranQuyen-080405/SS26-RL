"""
BLE UART — Robot (MicroPython bluetooth.BLE)
  TX 6e400003  notify  → PC: S:state JSON, L:log
  RX 6e400002  write   ← PC: S / START
"""

import bluetooth
from micropython import const

BLE_NAME = "Robot"
_SVC = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_CHAR_RX = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
_CHAR_TX = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

_FLAG_READ = const(0x0002)
_FLAG_NOTIFY = const(0x0010)
_FLAG_WRITE = const(0x0008)
_FLAG_WRITE_NO_RESP = const(0x0004)
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_ble = None
_conn = None
_tx_handle = None
_rx_handle = None
_start_flag = False
_adv_name = BLE_NAME


def _advertise(name):
    name_b = name.encode()
    uuid_b = bytes(_SVC)
    adv = bytearray((2, 0x01, 0x06))
    adv += bytearray((len(name_b) + 1, 0x09)) + name_b
    adv += bytearray((len(uuid_b) + 1, 0x07)) + uuid_b
    _ble.gap_advertise(100_000, adv_data=adv, connectable=True)


_MAX_NOTIFY = 240


def _notify(line):
    if _conn is None or _tx_handle is None or not line:
        return
    data = (line + "\n").encode()
    if len(data) > _MAX_NOTIFY:
        data = data[: _MAX_NOTIFY]
    try:
        _ble.gatts_notify(_conn, _tx_handle, data)
    except OSError:
        pass


def publish_log(text):
    if not text:
        return
    for part in str(text).split("\n"):
        part = part.strip()
        if part:
            _notify("L:" + part)


def _on_rx(data):
    global _start_flag
    if not data:
        return
    if data[0:1] == b"S":
        _start_flag = True
        publish_log("RX START (PC)")
        return
    try:
        if data.strip().upper() in (b"S", b"START"):
            _start_flag = True
            publish_log("RX START (PC)")
    except Exception:
        pass


def _irq(event, data):
    global _conn
    if event == _IRQ_CENTRAL_CONNECT:
        _conn, _, _ = data
    elif event == _IRQ_CENTRAL_DISCONNECT:
        _conn = None
        try:
            _advertise(_adv_name)
        except OSError:
            pass
    elif event == _IRQ_GATTS_WRITE:
        _, handle = data
        if _rx_handle is not None and handle == _rx_handle:
            try:
                _on_rx(_ble.gatts_read(_rx_handle))
            except OSError:
                pass


def start(name=BLE_NAME):
    """Bật BLE + UART GATT + advertising (giống bản step1 đã chạy OK)."""
    global _ble, _tx_handle, _rx_handle, _start_flag, _conn, _adv_name
    import time

    _start_flag = False
    _conn = None
    _tx_handle = None
    _rx_handle = None
    _adv_name = name

    _ble = bluetooth.BLE()
    try:
        if _ble.active():
            _ble.gap_advertise(None)
    except OSError:
        pass
    try:
        _ble.active(False)
    except OSError:
        pass
    time.sleep_ms(100)
    _ble.active(True)
    _ble.config(gap_name=name)
    try:
        _ble.gap_advertise(None)
    except OSError:
        pass

    # Không dùng max_len 512 — dễ OOM / crash trên xController
    handles = _ble.gatts_register_services(
        (
            (
                _SVC,
                (
                    (_CHAR_TX, _FLAG_READ | _FLAG_NOTIFY),
                    (_CHAR_RX, _FLAG_WRITE | _FLAG_WRITE_NO_RESP),
                ),
            ),
        )
    )
    _tx_handle = handles[0][0]
    _rx_handle = handles[0][1]
    _ble.irq(_irq)
    _advertise(name)
    print("BLE on —", name, "| TX h=%s RX h=%s" % (_tx_handle, _rx_handle))
    return True


def is_connected():
    return _conn is not None


def _walls_from_map(rmap):
    from modules.logics.grid import OBSTACLE_KEYS

    walls = []
    for (x, y), node in rmap["nodes"].items():
        for d in ("N", "W", "E", "S"):
            if node[OBSTACLE_KEYS[d]]:
                walls.append([x, y, d])
    return walls


def _compact_state(robot, phase="i", step=0, action=None):
    """Gói nhỏ (<240B) — PC đã có khung map; không gửi walls mỗi bước."""
    out = {
        "x": robot["x"],
        "y": robot["y"],
        "d": robot["direct"],
        "p": phase,
    }
    if step:
        out["n"] = step
    if action:
        out["a"] = action
    return out


def _publish_json_state(obj):
    import json

    try:
        payload = json.dumps(obj, separators=(",", ":"))
    except Exception:
        return
    if len(("S:" + payload + "\n").encode()) > _MAX_NOTIFY:
        return
    _notify("S:" + payload)


def publish_state(robot, phase="r", step=0, action=None):
    _publish_json_state(_compact_state(robot, phase=phase, step=step, action=action))


def publish_map_meta():
    """Gửi khung map (w/h/start/goal/checkpoints) — PC Robot Monitor đồng bộ layout."""
    import json

    try:
        from deploy_map import MAP_W, MAP_H, START, GOAL, CHECKPOINTS
    except ImportError:
        return
    obj = {
        "w": MAP_W,
        "h": MAP_H,
        "s": list(START),
        "g": list(GOAL),
        "c": [list(cp) for cp in CHECKPOINTS],
    }
    try:
        payload = json.dumps(obj, separators=(",", ":"))
    except Exception:
        return
    if len(("M:" + payload + "\n").encode()) > _MAX_NOTIFY:
        return
    _notify("M:" + payload)


def publish_idle(robot=None):
    if robot is None:
        from deploy_map import MAP_W, MAP_H, START, GOAL, CHECKPOINTS, WALLS
        from modules.logics.robot_map import init_robot_map, apply_walls_from_spec
        from modules.logics.robot_state import make_robot

        rmap = init_robot_map(MAP_W, MAP_H, goal=GOAL, checkpoints=CHECKPOINTS, start=START)
        apply_walls_from_spec(rmap, WALLS)
        robot = make_robot(START[0], START[1], "N", rmap)
    publish_state(robot, phase="i", step=0)
    publish_map_meta()


def pump(poll_ms=0):
    if poll_ms:
        import time

        time.sleep_ms(poll_ms)


def wait_for_connection(poll_ms=100):
    print("Cho PC ket noi BLE (robot_monitor)...")
    while not is_connected():
        pump(poll_ms)
    print("PC da ket noi BLE")
    try:
        publish_idle()
    except Exception as exc:
        print("publish_idle loi:", exc)


def wait_for_start(poll_ms=80):
    global _start_flag
    import time

    _start_flag = False
    has_btn = False
    try:
        from btn_onboard import btn_onboard

        has_btn = True
    except ImportError:
        btn_onboard = None

    if has_btn:
        while btn_onboard.is_pressed():
            pump(poll_ms)

    print("CHO START — nut board hoac Start infer tren PC.")
    last_idle = time.ticks_ms()

    while not _start_flag:
        if not is_connected():
            print("PC ngat — cho ket noi lai...")
            while not is_connected():
                pump(poll_ms)
            print("PC da ket noi lai")
            try:
                publish_idle()
            except Exception:
                pass
            last_idle = time.ticks_ms()
        elif time.ticks_diff(time.ticks_ms(), last_idle) > 3000:
            try:
                publish_idle()
            except Exception:
                pass
            last_idle = time.ticks_ms()
        if has_btn and btn_onboard.is_pressed():
            _start_flag = True
            print("Nhan nut onboard")
            break
        pump(poll_ms)

    publish_log("START OK — infer begin")
    _start_flag = False
