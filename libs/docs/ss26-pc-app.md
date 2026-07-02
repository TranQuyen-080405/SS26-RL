# SS26 — PC app (`main.py`)

> Entry point thống nhất: 4 tab. Spec triển khai — đủ làm lại UI shell.

---

## 1. Chạy

```bash
python main.py              # cả 4 tab
python create_map.py        # tab 0 — wrapper
python robot_monitor.py     # tab 3 — wrapper
```

Wrapper gọi `run_app(initial_tab=N)` từ `main.py`.

---

## 2. Cấu trúc tab

| Tab | Label | Module UI | Chức năng |
|-----|-------|-----------|-----------|
| 0 | Tạo map | `Ui_app/create_map_UI.py` → `MapEditorApp` | Vẽ cạnh map, lưu JSON `map/train/` hoặc `map/infer/` |
| 1 | Train / Infer | `Ui_app/rl_app_UI.py` → `RlApp` | Train Q, infer sim PC, animation map |
| 2 | State & Reward | `Ui_app/learn_lab_UI.py` → `LearnLabApp` | Ghép state, chỉnh reward, test kịch bản, xuất module đồng bộ |
| 3 | Robot Monitor | `main.py` → `RobotMonitorApp` | BLE robot thật — xem `ss26-ble-pipeline.md` |

`SS26App`: `ttk.Notebook`, một `tk.Tk`, embed panel qua `MapEditorApp(parent=frame, root=root)`.

Đóng app: `RobotMonitorApp.disconnect()` trước `destroy`.

---

## 3. Tab Tạo map

File: `Ui_app/create_map_UI.py`

- Grid click cạnh → toggle wall `(x,y,dir)`
- Spin width/height, start, goal, checkpoints
- Save → `map.map_io.save_map_json` → `map/train/map_*.json` hoặc `map/infer/`
- Load JSON từ thư mục tương ứng

Hằng vẽ: `CELL=44`, `MARGIN=24`. Hướng `N/W/E/S` theo `RL_lib/grid.py`.

**Không** liên kết BLE — map JSON dùng cho train/infer PC; robot deploy dùng map cố định 10×10 trong `makeRobot.py` (chưa load JSON từ file trên ESP32).

---

## 4. Tab Train / Infer

File: `Ui_app/rl_app_UI.py`, canvas `Ui_app/map_view.py` → `SimMapCanvas`.

- Mode train: `Simulation/rl_runner.run_train`, maps từ `map/train/`
  - **Random:** chọn map ✓ → mỗi episode `random.choice` trong tập đã chọn; tổng episodes = spinbox toolbar
  - **Lần lượt:** thứ tự ↑↓, cột Episodes/map → train map1 (N₁ ep) → map2 (N₂ ep) → …
  - Save map tab Tạo map → `notify_map_saved` → auto refresh train/infer list
- Mode infer: `run_infer_episode_for_map`, policy từ `Q_table/*.bin`
- View log hoặc map animation (ms/step spinbox)

Export policy sau train → `Q_table/policy.bin` → copy sang robot (`Robot_embbed/modules/logics/Q_table/`).

Thuật toán: `RL_lib/`, `Simulation/robot/` — xem `docs/ss26-strategy-RLtraining.md`.

---

## 5. Tab State & Reward (Learn Lab)

File: `Ui_app/learn_lab_UI.py`

| Layer | Module |
|---|---|
| UI map 12×5 + WASD | `Ui_app/lab_scenario_map.py`, `RL_lib/lab_world.py` |
| Catalog module/element | `RL_lib/lab_registry.py` |
| Reward runtime | `RL_lib/reward_config.py` |
| Công thức học sinh | `RL_lib/student_formula.py`, `Ui_app/formula_builder.py` |
| Lưu JSON | `RL_lib/formula_store.py` → `libs/reward_formula/*.json` |
| Kịch bản test | `RL_lib/lab_scenarios.py` |

**State:** bật/tắt module (`obstacle`, `goal`, `checkpoint`, `heading`, …) → preview `s` qua `encode_for_lab`.

**Reward:** học sinh ghép **label tiếng Việt** (vd. `Va chạm tường + Lặp ô gần`). Mỗi block trong công thức mới hiện spinbox weight + ngưỡng (nếu có).

**Explore penalty (module `explore_penalty`):**

| Block UI | Ngưỡng UI |
|---|---|
| Lặp ô gần | Số bước (`MAX_REVISIT_STEPS`) |
| Quay lại ô | Lần quay lại (`MAX_CELL_REPEAT`) |
| Đi qua đi lại liên tục | Chu kỳ qua lại + **Ô mỗi chiều** (`MAX_PING_PONG_CYCLES`, `MAX_PING_PONG_SPAN`) |

**Đồng bộ:**

| Hành động | Kết quả |
|---|---|
| **Lưu công thức** | JSON + patch `reward_config.py` + reload trainer |
| **Nạp** | `migrate_formula_snapshot` (tên cũ → mới) |
| **Apply → Train** | `reward_config.py` active cho `trainer.py` |

Train tab: `compute_reward` từ `reward_config.py`.  
ESP32 infer: **không** reward — chỉ `policy.bin` + `rl_core.py` (+ map cố định firmware).

Encoding `s`: cố định `RL_lib/rl_core.py` — Learn Lab không đổi công thức encode khi chỉnh reward.

---

## 6. Tab Robot Monitor

Toàn bộ BLE + map monitor nằm trong **`main.py`** (không file riêng logic).

Classes chính:

| Class | Vai trò |
|-------|---------|
| `MonitorMapModel` | Map 10×10 PC-side, merge BLE state |
| `RobotMapCanvas` | Vẽ grid, walls, robot, path |
| `RobotMonitorApp` | Scan, connect, Start infer, log, map |

Protocol BLE: **`docs/ss26-ble-pipeline.md`**.

---

## 6. Path Python

`main.py` đầu file:

```python
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, REPO_ROOT / "Simulation")
```

Các tab import `map.map_io`, `rl_runner`, `Ui_app.*` từ root này.

---

## 7. Phụ thuộc PC

| Package | Tab dùng |
|---------|----------|
| tkinter | Tất cả |
| bleak | Robot Monitor |
| (train) numpy/struct qua Simulation | Train/Infer |

---

## 8. Quan hệ PC ↔ Robot

```
Tab Train/Infer  →  policy.bin  →  upload ESP32
Tab Tạo map      →  map JSON    →  train PC (robot chưa đọc JSON)
Tab Monitor      →  BLE Start   →  makeRobot infer map cố định 10×10
```

Map hiển thị monitor **không** đọc file JSON; đồng bộ qua BLE `x,y,d` + khung cố định.

---

*Cập nhật theo `main.py`, `Ui_app/`, `create_map.py`, `robot_monitor.py`.*
