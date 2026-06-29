# SS26 — Đặc tả SimMap (Backward / Ground Truth)

> Spec **Simulation Map** — thay map thật trên PC để train policy (backward).  
> Policy train xong chạy trên robot thật với **cùng hành vi** (3 action, cùng state encode).  
> Bám brainstorm [SS26 Planning Nhìn công](../SS26%20Planning%20Nhìn%20công.txt) (dòng 11–30).

**Quan hệ với Robot spec:** [s26-strategy-Robot.md](./s26-strategy-Robot.md)  
**Quan hệ với RL:** [ss26-strategy-RLtraining.md](./ss26-strategy-RLtraining.md)

---

## 1. Vai trò SimMap

```
┌─────────────────────────────────────────────────────────┐
│                    TRAINER (PC only)                     │
│  ┌──────────┐    oracle     ┌──────────┐                │
│  │  SimMap  │──────────────►│  Robot   │                │
│  │ (truth)  │  read_block   │          │                │
│  └──────────┘  manhattan    └────┬─────┘                │
│       │                          │                       │
│       │ goal, walls, CP          │ chỉ thấy             │
│       ▼                          ▼                       │
│  reward, reset              ┌──────────┐                │
│                             │ RobotMap │  memory        │
│                             └──────────┘                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    ESP32 (deploy)                        │
│  Không có SimMap — chỉ RobotMap + Policy + sensors       │
└─────────────────────────────────────────────────────────┘
```

| | SimMap | RobotMap |
|---|---|---|
| **Instance** | `sim_map` — một object riêng | `robot_map` — object riêng |
| **Class** | `Map` (cùng class) | `Map` (cùng class) |
| **Ai truy cập** | Trainer, test harness | Robot |
| **Ground truth** | Có — `edge.isBlock`, goal, CP | Không — chỉ perception |
| **Node obstacle field** | Không bắt buộc | Có — `N/W/E/S_obstacle` |
| **Khi deploy** | Không có trên ESP32 | Có trên robot |

**Nguyên tắc:** Train trên SimMap sao cho **transition** `(s, a, s')` và **sensor oracle** giống robot thật → policy transfer được.

---

## 2. Cùng class, hai instance

### 2.1 Class dùng chung

| Class | File đề xuất | Ghi chú |
|---|---|---|
| `Node` | `RL_lib/grid.py` (khái niệm) | Base + optional robot fields |
| `Edge`, `NS_edge`, `WE_edge` | map sim | `isBlock` = vật lý |
| `Map` | `Simulation/map/sim_map.py` | Graph lưới |

Hiện tại code tách `Simulation/map/` và `Simulation/robot/modules/node.py` — spec yêu cầu **gộp một định nghĩa**, tạo hai instance:

```python
sim_map = Map(width=10, height=10)      # Trainer
robot_map = Map(width=10, height=10)    # Robot memory — khởi tạo độc lập
```

### 2.2 Node — hai “chế độ” trên cùng class

```python
class Node:
    # --- chung (SimMap + RobotMap) ---
    x, y, id
    neighbor_id(), neighbor_xy()

    # --- RobotMap only (SimMap để mặc định) ---
    N_obstacle, W_obstacle, E_obstacle, S_obstacle = 0,0,0,0
    dist_goal: int | None = None
    dist_checkpoint: list[int] | None = None
```

Trên **SimMap**, không dùng `*_obstacle` để quyết định vật lý — dùng `edge.isBlock`.

Trên **RobotMap**, `*_obstacle` cập nhật qua `Robot.perceive_edge()`.

---

## 3. Class `Edge` (ground truth)

Brainstorm: *"node[x][y] có N_obstacle = 1 thì node[x][y+1] có S_obstacle = 1"* — trên SimMap, nguồn gốc là **cạnh bị chặn**, không phải node đơn lẻ.

### 3.1 Thuộc tính

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `node1`, `node2` | `Node` | Hai đầu cạnh |
| `isBlock` | `bool` | **Ground truth** — tường trên bạt |

### 3.2 Loại cạnh

| Class | Nối | Validate id |
|---|---|---|
| `NS_edge` | Bắc–Nam | `N.id == S.id + 10` |
| `WE_edge` | Tây–Đông | `E.id == W.id + 1` |

### 3.3 Phương thức

```python
def get_block() -> bool
def set_block(value: bool) -> None
def has_node(node) -> bool
def get_neighbor(node, direction) -> Node | None
```

### 3.4 Đồng bộ obstacle (khi trainer inject perception)

Khi trainer gọi `robot.perceive_edge(sim_map.read_block(...))`:

```
SimMap edge.isBlock (truth)
    → RobotMap edge.isBlock (memory copy)
    → RobotNode.N_obstacle + neighbor.S_obstacle (đồng bộ)
```

SimMap **không** cần mirror `*_obstacle` trên node trừ khi debug UI.

---

## 4. Class `Map` — instance `SimMap`

**File:** `Simulation/map/sim_map.py`

### 4.1 Thuộc tính (kế thừa graph + thêm mission)

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `width`, `height` | `int` | Kích thước bạt / lưới |
| `nodes`, `nodes_by_id`, `edges` | — | Graph |
| `goal` | `(int, int)` | Ô đích |
| `checkpoints` | `list[(int,int)]` | 1–3 CP tùy layout; **không bắt buộc thứ tự** ghé |
| `start` | `(int, int)` | Vị trí reset robot |
| `walls` | `list` optional | Cache cạnh block để load map |

### 4.2 Phương thức graph (dùng chung RobotMap)

```python
def add_node(x, y) -> Node | None
def get_node(x, y) -> Node | None
def get_neighbor(node, direction) -> Node | None
def get_edge_between(node_a, node_b) -> Edge | None
def get_edge_in_direction(node, direction) -> tuple[Node|None, Edge|None]
def auto_link() -> None
```

### 4.3 Phương thức chỉ SimMap / Trainer

```python
def read_block(x: int, y: int, direction: str) -> bool:
    """
    Oracle cho sensor: cạnh từ (x,y) theo direction có bị chặn không.
    - Không có neighbor (biên map) → True (coi như tường)
    - Không có edge → True
    - else → edge.get_block()
    """

def set_wall(x, y, direction, blocked: bool) -> None:
    """Đặt tường ground truth; tạo/cập nhật edge.isBlock."""

def manhattan(x1, y1, x2, y2) -> int:
    return abs(x1 - x2) + abs(y1 - y2)

def dist_to_goal(x, y) -> int:
    return manhattan(x, y, goal[0], goal[1])

def dist_to_checkpoints(x, y) -> list[int]:
    return [manhattan(x, y, cx, cy) for cx, cy in checkpoints]

def is_at_goal(x, y) -> bool:
    return (x, y) == goal

def is_at_checkpoint(x, y, index: int) -> bool:
    return (x, y) == checkpoints[index]

def can_move(x, y, direction) -> bool:
    """not read_block(x,y,direction) — dùng trước khi simulate forward."""

def reset_robot(robot: Robot) -> None:
    """
    Đặt robot về start, direct mặc định.
    RobotMap: xoá obstacle memory (hoặc tạo RobotMap mới).
    """
```

### 4.4 Load map từ đề bài

```python
@classmethod
def from_layout(cls, layout: dict) -> Map:
    """
    layout ví dụ:
    {
      "width": 10, "height": 10,
      "start": [0, 0], "goal": [9, 9],
      "checkpoints": [[2,2], [5,5]],
      "walls": [
        {"x": 3, "y": 4, "dir": "E", "block": true},
        ...
      ]
    }
    """
```

---

## 5. Hành vi simulation = hành vi robot thật

Để policy transfer, trainer phải mô phỏng **đúng contract** của robot:

| Hành vi | Robot thật | SimMap + harness phải làm |
|---|---|---|
| Quét tường | Ultrasonic hướng `direct` | `read_block(x,y,direct)` → `perceive_edge` |
| Tiến 1 node | Line array → pattern `1111` | `Action.forward` chỉ khi `not read_block` |
| Xoay | 90° tại chỗ | Chỉ đổi `direct` |
| Không thấy hướng khác | Chỉ obs hướng đang nhìn | Không leak toàn map vào state |
| Partial observability | RobotMap obstacle ban đầu = 0 | Reset memory mỗi episode |

**Cấm:** Đưa `sim_map` vào `Robot` hoặc nhét full map vào `State.encode()`.

---

## 6. Trainer harness — cầu nối SimMap ↔ Robot

**File đề xuất:** `Simulation/robot/modules/trainer.py`

```python
class SimHarness:
  def __init__(self, sim_map: Map, robot: Robot):
      self.sim_map = sim_map
      self.robot = robot

  def oracle_perceive(self) -> None:
      """Đọc truth từ sim_map, ghi vào robot_map qua robot."""
      blocked = self.sim_map.read_block(
          self.robot.x, self.robot.y, self.robot.direct
      )
      self.robot.perceive_edge(blocked)

  def inject_distances(self) -> None:
      dg = self.sim_map.dist_to_goal(self.robot.x, self.robot.y)
      dcp = self.sim_map.dist_to_checkpoints(self.robot.x, self.robot.y)
      self.robot.refresh_distances(dg, dcp)

  def simulate_forward(self) -> ActionResult:
      """Action.forward nhưng validate bằng sim_map.can_move."""
      ...

  def compute_reward(self, s, a, s_prime, info) -> float:
      """Dùng sim_map.is_at_goal, dist trends, blocked..."""
      ...
```

Luồng một bước train:

```
1. oracle_perceive()          # trước hoặc sau rotate tuỳ spec
2. inject_distances()
3. s = robot.encode_state()
4. a = epsilon_greedy(s)
5. result = execute_action(a)  # forward kiểm tra sim_map.can_move
6. inject_distances(); s' = robot.encode_state()
7. r = compute_reward(s, a, s', result)
8. Q.update(s, a, r, s')
```

---

## 7. Reward — input từ SimMap

Reward tính trên trainer (có SimMap), không trên robot.

| Sự kiện | Nguồn SimMap |
|---|---|
| Tới goal | `is_at_goal(x,y)` |
| Gần/xa goal | `dist_to_goal` trước/sau action |
| Checkpoint | `is_at_checkpoint`, `cp_visited` — **+điểm 1 lần**/CP/episode |
| Đụng tường | `read_block` True khi forward |
| Hết bước | `step_count >= max_steps` |

Chi tiết bảng điểm: [ss26-strategy-RLtraining.md §4.1](./ss26-strategy-RLtraining.md).

---

## 8. Episode lifecycle

```
1. sim_map.reset_robot(robot)
   - robot.x,y = sim_map.start
   - robot_map = Map mới hoặc clear obstacle
2. Loop đến done:
   - harness step + Q update
3. done khi:
   - is_at_goal
   - max_steps
   - robot kẹt (optional)
4. Cuối train: export `policy.json` + `policy.bin` → deploy ESP32
```

**Train nhiều map:** Mỗi episode `sim_map = Map.from_layout(random_layout())`; `robot_map` reset cùng kích thước.

---

## 9. Đồng bộ kích thước SimMap ↔ bạt thật

| Tham số | SimMap | Robot thật |
|---|---|---|
| `width`, `height` | Từ file đề / layout | Cùng giá trị khi học sinh nộp map |
| `id = y*10+x` | Cố định | Cùng công thức |
| Vị trí start/goal | Layout JSON | Marker / config robot |

Học sinh train trên layout giống bạt thi đấu → policy không cần biết tọa độ tuyệt đối trong Q, chỉ cần **cùng state encode**.

---

## 10. Ví dụ map nhỏ (minh hoạ)

```
Layout 5×5, start (0,0), goal (4,4)
Wall: (2,2)-E blocked

SimMap:
  set_wall(2, 2, "E", True)
  → NS/WE edge isBlock=True
  → read_block(2,2,"E") == True

RobotMap (ban đầu):
  mọi *_obstacle = 0

Sau robot đứng (2,2) nhìn E, perceive:
  robot_map node (2,2).E_obstacle = 1
  robot_map node (3,2).W_obstacle = 1
```

---

## 11. Mapping file hiện tại → spec

| Spec | File hiện tại | Ghi chú |
|---|---|---|
| `SimMap` / `Map` | `Simulation/map/map.py` | Thiếu goal, CP, `from_layout` |
| `Node` (sim) | `Simulation/map/node.py` | Chỉ x,y,id — đúng hướng |
| `Edge` | `Simulation/map/node.py` | Có NS/WE |
| `read_block` | `map.py` | Đã có |
| `RobotMap` | `robot/modules/node.py` | Trùng Map — cần tách instance |
| Trainer harness | chưa có | Cần tạo |

---

## 12. Khác biệt cần sửa so với code hiện tại

1. **Hai Map trùng code nhưng không merge object** — `Robot.map` không trỏ `Simulation/map.Map` train.  
2. **Edge trên RobotMap** — bật lại class `Edge` (đang comment trong `robot/modules/node.py`) để `perceive` hoạt động.  
3. **SimMap Node không cần obstacle** — truth chỉ trên edge; tránh duplicate logic.  
4. **Trainer** — mọi đọc ground truth đi qua `SimHarness`, không cheat vào `State`.  
5. **Biên map** — `read_block` ở rìa trả `True` (tường ảo) giống rơi khỏi bạt.

---

## 13. Thứ tự implement (SimMap side)

1. Map sim + robot_map (hàm thuần) — logic lưới trong `RL_lib/grid.py`  
2. Thêm `goal`, `checkpoints`, `start` + `from_layout`  
3. `set_wall`, `can_move`, `dist_to_*`  
4. `SimHarness.oracle_perceive` + `inject_distances`  
5. Nối `Trainer.run_episode` với Q-learning  
6. Test: một map tay, robot chỉ đi được khi perceive đúng  
7. Export policy → chạy lại chỉ với harness (không train) để verify forward  

---

## 14. Quyết định liên quan (xem RL spec §8)

1. Checkpoint **1–3** tùy map; không bắt buộc thứ tự; điểm **1 lần**/CP.  
2. Train: map cố định trước → curriculum nhiều map (config sau).  
3. Còn mở: **Train multi-map** — file pool layout; tường trên edge hay ô?  

---

*Spec: `docs/s26-strategy-simMap.md` — SimMap ground truth và backward training.*
