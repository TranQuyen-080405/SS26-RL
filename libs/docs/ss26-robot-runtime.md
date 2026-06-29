# SS26 — Robot runtime (ESP32) — spec triển khai

> Mô tả **đúng code đang chạy** trên `Robot_embbed/`. Đủ để làm lại boot → BLE → Start → infer mà không đoán.  
> Thuật toán RL/encode: `docs/ss26-strategy-RLtraining.md`. Map memory: `docs/s26-strategy-Robot.md`.  
> BLE + PC monitor: `docs/ss26-ble-pipeline.md`.

---

## 1. File và thứ tự gọi

```
Robot_embbed/main.py
  → ble_monitor.start()
  → ble_monitor.wait_for_connection()
  → ble_monitor.wait_for_start()
  → logic.run()  →  makeRobot.run()
```

| File | Vai trò |
|------|---------|
| `main.py` | Boot, gate infer, bắt crash → `publish_log` |
| `modules/server/ble_monitor.py` | GATT Nordic UART, RX Start, TX log/state |
| `modules/makeRobot.py` | Map cố định 10×10, vòng infer, publish BLE |
| `modules/logics/logic.py` | Re-export `makeRobot.run` |
| `modules/logics/action.py` | `run_policy_step`, `forward_hw` / rotate (placeholder motor) |
| `modules/logics/policy_io.py` | Load `policy.bin` bằng **memoryview** (bắt buộc trên ESP32) |
| `modules/logics/readSensor.py` | `read_obstacle`, `read_line` |
| `modules/logics/robot_map.py` | `init_robot_map`, `apply_boundary_walls`, `can_move` |
| `modules/logics/robot_state.py` | Dict robot, `build_encoded_state`, trends |
| `modules/logics/rl_core.py` | `encode_state`, `N_ROWS`, `ACTIONS` — sync từ `RL_lib/` |
| `modules/logics/Q_table/policy.bin` | Policy deploy từ PC (`Q_table/policy.bin`) |

**Không infer khi boot:** `main.py` không gọi `run()` trước `wait_for_start()`.

---

## 2. Hằng số map (phải khớp PC monitor)

Trong `makeRobot.py`:

```python
MAP_W = 10
MAP_H = 10
START = (0, 0)
GOAL = (9, 9)          # MAP_W - 1, MAP_H - 1
CHECKPOINTS = []
```

Khởi tạo:

```python
rmap = init_robot_map(MAP_W, MAP_H, goal=GOAL, checkpoints=CHECKPOINTS, start=START)
bot = make_robot(START[0], START[1], "N", rmap)
inject_distances_from_map(bot)
```

`init_robot_map` gọi `apply_boundary_walls` — mép map = obstacle trong `robot_map` memory.

---

## 3. Policy trên ESP32 (RAM)

**Không** tạo `list` 5184×3 float trên MicroPython — OOM, infer treo im lặng sau log đầu.

`policy_io.load_policy_bin(path)`:

1. `open(path,"rb").read()` → bytes
2. Kiểm tra `len(data) == N_ROWS * len(ACTIONS) * 4` (62208 byte với spec hiện tại)
3. `_POLICY_MV = memoryview(data)` — global
4. Trả `True` / `False`

`get_policy_for_state(encoded_state)`:

```python
base = encoded_state * 3 * 4
q0, q1, q2 = struct.unpack_from("<3f", _POLICY_MV, base)
# argmax → ACTIONS[i]
```

PC train export: `Q_table/policy.bin` → copy sang `Robot_embbed/modules/logics/Q_table/policy.bin`.

---

## 4. Một bước infer — `run_policy_step(robot)`

File: `modules/logics/action.py`

```
1. obs = read_obstacle(port=1)     # try/except → None nếu lỗi
2. if obs is not None:
       perceive_edge(robot, bool(obs))   # hướng = robot["direct"]
3. s = build_encoded_state(robot)
4. name = get_policy_for_state(s)
5. result = execute_action(robot, name)
6. return (name, result)
```

### 4.1 `read_obstacle` (`readSensor.py`)

```
sleep 30ms
dist = ultrasonic.distance_cm(port)
dist >= 200  → None   (không chặn / không đo)
dist < 8     → 1      (chặn)
else         → None
```

### 4.2 `execute_action` → result dict

| Action | Motor (hiện tại) | result |
|--------|------------------|--------|
| `forward` | **Placeholder:** `_commit_forward` ngay (chưa `read_line`) | `{success, moved, collision}` |
| `rotate left/right` | **Placeholder:** chỉ `update_direction` | `{success, moved: False, collision: False}` |

`forward_hw`:

1. `can_move(robot_map, x, y, d)` — mép / obstacle memory
2. `read_obstacle` lần 2 — ultrasonic
3. `_commit_forward` — cập nhật x,y, dist, trend

`collision=True` → vòng `makeRobot` dừng, BLE `p:"c"`.

### 4.3 TODO motor (chưa làm — không đổi logic RL)

- Forward: `forward_action` + loop `read_line(port)=="node"` rồi mới `_commit_forward`
- Rotate: `turn_left_angle(90)` / `turn_right_angle(90)`

---

## 5. Vòng infer — `makeRobot.run()`

```
load_policy_bin(...) → fail → log + return

step = 0
publish_log("infer loop — policy loaded")
publish_state(bot, phase="r", step=0)
pump(50)

while True:
    if is_at_goal(bot):
        publish_log("GOAL — tới đích")
        publish_state(bot, phase="g", step=step)
        break

    step += 1
    try:
        action, result = run_policy_step(bot)
    except Exception as exc:
        publish_log("step N ERROR: ...")
        publish_state(bot, phase="c", step=step)
        break

    publish_state(bot, phase="r", step=step, action=action)
    publish_log("step N | (x,y) d | action [COLLISION]")
    if result["collision"]:
        publish_state(bot, phase="c", step=step, action=action)
        break
    pump(80)    # nhường CPU + BLE giữa các bước
```

Mọi log quan trọng: `print` serial **và** `publish_log` (nếu import được `ble_monitor`).

---

## 6. Boot + gate Start

### 6.1 `ble_monitor.start()`

- Stack: `bluetooth.BLE()` (MicroPython), **không** dùng song song xController `ble` module.
- Service Nordic UART (xem `ss26-ble-pipeline.md`).
- **Không** đăng ký `max_len=512` trên characteristic — gây OOM / không advertise trên xController.
- Advertising name: `"Robot"`.

### 6.2 `wait_for_connection()`

Block đến khi `_conn` set (IRQ connect). Gửi `publish_idle()` → state `p:"i"`.

### 6.3 `wait_for_start()`

Block đến khi `_start_flag`:

- PC ghi RX: byte `b"S"` hoặc chuỗi `START`
- Hoặc nút onboard (`btn_onboard`) nếu import được

Trong vòng chờ: mỗi 3s gửi lại idle; mất kết nối → chờ reconnect.

Khi thoát: `publish_log("START OK — infer begin")`, reset `_start_flag`.

---

## 7. Đồng bộ với PC

Robot **không** gửi full `walls` JSON (vượt 240 byte notify). PC giữ khung map 10×10 + tường biên; robot chỉ gửi `x,y,d,p,n,a`.

Chi tiết protocol: `docs/ss26-ble-pipeline.md`.

---

## 8. Checklist upload firmware

```
Robot_embbed/main.py
Robot_embbed/modules/makeRobot.py
Robot_embbed/modules/server/ble_monitor.py
Robot_embbed/modules/logics/action.py
Robot_embbed/modules/logics/policy_io.py
Robot_embbed/modules/logics/readSensor.py
Robot_embbed/modules/logics/          # grid, rl_core, robot_map, robot_state
Robot_embbed/modules/logics/Q_table/policy.bin
```

Serial kỳ vọng:

```
BLE on — Robot | TX h=... RX h=...
Cho PC ket noi BLE (robot_monitor)...
PC da ket noi BLE
CHO START — nut board hoac Start infer tren PC.
infer start
infer loop — policy loaded
step 1 | ...
```

---

## 9. Không được phá (regression)

| Quy tắc | Lý do |
|---------|--------|
| Policy ESP32 = memoryview, không list-of-lists | RAM |
| BLE notify ≤ 240 byte / dòng; state compact, không walls | MTU notify xController |
| Không `max_len=512` GATT khi register service | OOM advertise |
| `wait_for_start` trước `makeRobot.run` | Không auto-infer |
| `MAP_*` / `START` / `GOAL` khớp `main.py` PC | Map monitor |
| Sửa `RL_lib/rl_core.py` → copy sang `Robot_embbed/modules/logics/rl_core.py` | Cùng `encode_state` / `N_ROWS` |

---

*Cập nhật theo codebase SS26-RL — robot runtime.*
