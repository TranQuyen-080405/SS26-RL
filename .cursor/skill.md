---
name: ss26-rl-architecture
description: >-
  SS26 RL robot/sim codebase — locked architecture, pure-function logic, RL_lib,
  Simulation vs Robot_embbed split. Use when editing Simulation/, Robot_embbed/,
  RL_lib/, policy train/deploy, encode_state, or get_policy. Do not refactor
  core logic unless the user explicitly asks to debug or change architecture.
---

# SS26 RL — Kiến trúc đã chốt

## Quy tắc bắt buộc cho agent

1. **Không đổi logic lõi** (encode, policy, map memory, luồng infer/train) trừ khi user nói rõ *debug*, *đổi spec*, hoặc *refactor architecture*.
2. **Không thêm OOP** cho phần robot/sim logic — chỉ **hàm thuần + dict**.
3. **Không gộp** `Simulation/` và `Robot_embbed/` thành một runtime; **không** bỏ `Robot_embbed/` (cần cho ESP32).
4. Sửa `RL_lib/` → **sync** bản copy sang `Robot_embbed/modules/logics/` (`grid.py`, `rl_core.py`).
5. Chi tiết reward/train/map: đọc `docs/ss26-strategy-RLtraining.md`, `docs/s26-strategy-Robot.md`, `docs/s26-strategy-simMap.md` — không đổi quyết định §8 trừ khi user yêu cầu.

---

## Hai môi trường

| | PC (`Simulation/` + `RL_lib/`) | Mạch (`Robot_embbed/`) |
|---|---|---|
| Vai trò | Train backward, sim, export policy | Infer forward, sensor, motor |
| Học Q | Có (`trainer.py`) | **Không** |
| SimMap GT | Có (`map/sim_map.py`) | **Không** |
| Policy | Tạo `Q_table/policy.json` + `Q_table/policy.bin` | Chỉ **đọc** `Q_table/policy.bin` (ưu tiên) |

```
PC: State → encode → Q-update → export Q_table/policy.bin
ESP32: sensor → State → encode → get_policy → action (motor)
```

---

## Cây thư mục logic (đã chốt)

```
RL_lib/                          # Nguồn chuẩn thuật toán trên PC
  grid.py                        # N/W/E/S, neighbor_xy, turn_left/right
  rl_core.py                     # dist_trend, encode_state, get_policy, N_ROWS

Simulation/
  map/sim_map.py                 # Ground truth: init, set/clear/get wall, goal, CP
  robot/
    robot_map.py                 # Robot memory: node obstacle, dist_*
    robot.py                     # Dict robot: trends, build_encoded_state
    action.py                    # execute_action_sim (+ hw stub cho test)
    policy_io.py                 # load + export json/bin
    trainer.py                   # Q-learning 1 map (curriculum/multi-map sau)
  run_demo.py

Robot_embbed/modules/logics/     # Copy sync từ RL_lib + mirror robot/*
  grid.py, rl_core.py
  robot_map.py, robot_state.py   # robot_state (không đặt tên robot.py — trùng motor API)
  action.py                      # forward_hw, _commit_forward, TODO motor
  policy_io.py                   # load only
  readSensor.py
  logic.py                       # run_policy_step loop
```

**Không tồn tại / đã xóa:** class `Robot`, `Policy`, `State`, `Map`, `Node`, folder `shared/`.

---

## Concept lõi

### Hai map — hai object, cùng kiểu dữ liệu (dict)

- **`sim_map`** (chỉ PC): ground truth `walls`, `goal`, `checkpoints`. Oracle: `get_block(x,y,dir)`.
- **`robot_map`** (PC + ESP32): memory robot. Node có `N/W/E/S_obstacle`, `dist_goal`, `dist_checkpoint[3]`.
- Robot **không** trỏ `sim_map` lúc deploy; lúc train, harness inject sensor từ sim vào `robot_map`.

### Robot = dict

```python
{"x", "y", "direct", "robot_map", "prev_dist_*", "dist_*_trend", "has_prev_node", "cp_visited"}
```

### State encode (PC ≡ ESP32)

Thành phần: `obstacle[N,W,E,S]` (map frame) + `dist_goal_trend` + `dist_cp_trend[0..2]` + `heading` (`direct`).

- `N_cp_max = 3` cố định; map có 1–2 CP → slot thừa `dist_cp_trend[i]=0`.
- `dist_trend(truoc, sau)`: sau < truoc → +1 (gần); sau > truoc → -1; bằng → 0.
- Khoảng cách tuyệt đối chỉ lưu trên node để tính trend; **không** đưa vào encode.

```
N_ROWS = 16 × 3^4 × 4 = 5184
s = obstacle_bits × 324 + trend_packed × 4 + heading_idx
```

3 action: `forward`, `rotate left`, `rotate right`.  
`get_policy(s, Q)` = argmax hàng `Q[s]`; tie-break: forward > rotate left > rotate right.

### Checkpoint & train (đã chốt — docs §8)

- CP: **1–3** tùy layout.
- **Không** bắt buộc thứ tự; **+điểm 1 lần**/CP/episode (`cp_visited`).
- Train: **phase 1** một map cố định → **phase 2** curriculum + multi-map (config sau).
- Export: **đồng thời** `Q_table/policy.json` + `Q_table/policy.bin`.

---

## Luồng infer (mỗi bước policy)

```
1. perceive_edge (ultrasonic / sim get_block)
2. (sau forward) compute trends từ prev_dist vs node hiện tại
3. s = build_encoded_state(robot)
4. action = get_policy(s, Q)
5. execute action
```

### Forward

| | Simulation | ESP32 |
|---|---|---|
| Kiểm tra tường | `sim_map.can_move` | `read_obstacle()` |
| Di chuyển | `update_position` ngay | TODO motor + `read_line()=="node"` **trước** `_commit_forward` |
| Cập nhật state | snapshot → position → inject dist → trends → mark_moved | **`_commit_forward`** — cùng khối logic |

### Rotate

Chỉ `update_direction`; không đổi (x,y). ESP32: TODO `turn_*_angle(90)`.

---

## File nào phải giống nhau (sync)

| RL_lib (PC) | Robot_embbed (copy) |
|---|---|
| `grid.py` | `modules/logics/grid.py` |
| `rl_core.py` | `modules/logics/rl_core.py` |
| `robot_map.py` | `modules/logics/robot_map.py` |
| `robot.py` | `modules/logics/robot_state.py` |

`policy_io.load_policy_bin` — cùng format; PC thêm `export_policy`.

---

## Chỉ Simulation / chỉ ESP32

**Chỉ PC:** `sim_map.py`, `trainer.py`, `export_policy`, `run_demo.py`.

**Chỉ ESP32:** `readSensor.py`, `action.forward_hw` (motor TODO), `logic.py`, `modules/server/`, `UI/`.

---

## Khi được phép sửa

| User nói | Được làm |
|---|---|
| Bug / debug / fix lỗi cụ thể | Sửa tối thiểu trong phạm vi bug |
| Nối motor, sensor node | Chỉ `action.py`, `readSensor.py`, `logic.py` — **không** đổi encode |
| Train curriculum, config map | `trainer.py`, config — không đổi `rl_core` |
| Đổi spec RL / state | User phải nói rõ; cập nhật `RL_lib` + docs + embed copy |

| Không làm khi không được hỏi |
|---|
| Đổi công thức `encode_state` / `N_ROWS` |
| Thêm class OOP cho robot/map |
| Merge Simulation + Robot_embbed |
| Đổi tên `RL_lib` hoặc xóa duplicate embed mà không có kế hoạch flash |

---

## Test nhanh sau thay đổi RL_lib

```bash
python Simulation/tests/test_rl_core.py
python Simulation/run_demo.py   # tạo Q_table/policy.json + Q_table/policy.bin
```

---

## Tài liệu tham chiếu

- `docs/ss26-strategy-RLtraining.md` — encode, reward, train, export
- `docs/s26-strategy-Robot.md` — robot map, infer loop
- `docs/s26-strategy-simMap.md` — SimMap GT, harness train
- `SS26 Planning Nhìn công.txt` — brainstorm gốc
