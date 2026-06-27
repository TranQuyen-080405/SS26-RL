# SS26 — Đặc tả Robot (Forward / Inference)

> Spec lớp Robot và các object liên quan trên **robot thật (ESP32)** và **simulation khi chạy policy**.  
> Bám brainstorm [SS26 Planning Nhìn công](../SS26%20Planning%20Nhìn%20công.txt) (dòng 11–30).  
> Phần train backward và SimMap ground truth: xem [s26-strategy-simMap.md](./s26-strategy-simMap.md).  
> Phần Q-learning / reward: xem [ss26-strategy-RLtraining.md](./ss26-strategy-RLtraining.md).

---

## 1. Nguyên tắc thiết kế

### 1.1 Robot không biết map thật

Robot chỉ tương tác với **`RobotMap`** — bản đồ trong memory, được xây dần qua cảm biến.

| Object | Ai sở hữu | Vai trò |
|---|---|---|
| `RobotMap` | Robot | Memory: obstacle đã thấy, khoảng cách cache, node hiện tại |
| `SimMap` | Trainer (PC only) | Ground truth để train — **robot không truy cập** |

Hai map là **hai instance khác nhau**, cùng class `Map` (xem simMap spec).

### 1.2 Hướng chuẩn

Brainstorm ghi `[W, S, N, D]` — trong spec dùng **`N, W, E, S`** (Đông = `E`).

```
        N (y+1)
         ↑
W (x-1) ←●→ E (x+1)
         ↓
        S (y-1)
```

Quy luật `node.id = y * 10 + x` (cố định theo đề):

| Hướng | Delta id | Delta (x, y) |
|---|---|---|
| N | +10 | (0, +1) |
| S | −10 | (0, −1) |
| E | +1 | (+1, 0) |
| W | −1 | (−1, 0) |

### 1.3 Ba action trừu tượng

| Action | Ý nghĩa logic | Robot thật | Simulation |
|---|---|---|---|
| `forward` | Tiến 1 node theo `direct` | `follow_line` đến khi `read_line → "node"` | Nhảy sang neighbor nếu cạnh không block |
| `rotate left` | Xoay 90° trái | `robot.turn_left_angle(90)` | `_update_direction("left")` |
| `rotate right` | Xoay 90° phải | `robot.turn_right_angle(90)` | `_update_direction("right")` |

Policy **không** gọi motor trực tiếp — luôn qua `Robot.execute_action()`.

---

## 2. Sơ đồ tương tác

```
                    ┌─────────────┐
                    │   Policy    │  get_policy(encoded_state, Q)
                    └──────┬──────┘
                           │ action name
                    ┌──────▼──────┐
                    │    Robot    │
                    │  x,y,direct │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │   Action    │ │ RobotMap    │ │   State     │
    │ (motor/sim) │ │ (memory)    │ │ encode()    │
    └─────────────┘ └──────┬──────┘ └─────────────┘
                           │
                    ┌──────▼──────┐
                    │ RobotNode   │  obstacle, dist_*
                    └─────────────┘
```

**Vòng lặp inference (mỗi quyết định policy):**

```
1. perceive()        — quét cạnh theo hướng direct (nếu cần)
2. build_state()     — đọc RobotNode + trend khoảng cách
3. encode()          — số nguyên cho Q-table
4. get_policy(s)     — chọn action
5. execute_action()  — forward / rotate
6. on_node_reached() — cập nhật x,y; lưu dist cũ cho trend
```

---

## 3. Class `Robot`

**File đề xuất:** `Simulation/robot/robot.py`, `Robot_embbed/modules/logics/logic.py` (orchestrator)

### 3.1 Thuộc tính

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `x`, `y` | `int` | Vị trí node hiện tại trên lưới |
| `direct` | `"N"\|"W"\|"E"\|"S"` | Hướng robot đang nhìn |
| `robot_map` | `Map` | **Chỉ** RobotMap instance |
| `current_node` | `Node` | `robot_map.get_node(x, y)` — cache, cập nhật khi di chuyển |
| `policy` | `Policy` / `Q` | Bảng Q đã load (ESP32: từ Flash) |
| `prev_dist_goal` | `int \| None` | Khoảng cách goal ở node trước — tính trend |
| `prev_dist_cp` | `list[int]` | Tương tự cho từng checkpoint |
| `at_goal` | `bool` | Đã tới goal chưa |

### 3.2 Phương thức bắt buộc

#### Vị trí & hướng

```python
def get_position(self) -> tuple[int, int]:
    """Trả (x, y)."""

def get_direction(self) -> str:
    """Trả direct hiện tại."""

def _update_direction(self, turn: Literal["left", "right"]) -> None:
    """
    Xoay 90° trong không gian map (không di chuyển x,y).
    left:  N→W→S→E→N
    right: N→E→S→W→N
    """

def _update_position(self, x: int, y: int) -> None:
    """
    Gọi khi xác nhận đã tới node mới.
    - Cập nhật self.x, self.y, self.current_node
    - Trên robot thật: chỉ gọi khi sensor báo "node" (line_array 1111)
    """
```

#### Perception & state

```python
def perceive_edge(self, is_blocked: bool) -> None:
    """
    Nhìn theo self.direct, cập nhật obstacle vào RobotMap.
    - is_blocked: từ sensor thật HOẶC sim oracle (trainer inject)
    - Gọi current_node.perceive(direct, is_blocked, edge)
    - Đồng bộ neighbor: node[x,y].N_obstacle=1 → node[x,y+1].S_obstacle=1
    """

def read_obstacle_ahead(self) -> bool | None:
    """
    Platform-specific:
    - ESP32: ultrasonic < ngưỡng → True (block), None nếu chưa đo
    - Sim: trainer gọi sim_map.read_block(x,y,direct) rồi truyền vào perceive_edge
  Không đọc trực tiếp SimMap trong class Robot trên ESP32.
    """

def refresh_distances(self, dist_goal: int, dist_cp: list[int]) -> None:
    """
    Ghi dist_goal, dist_checkpoint vào current_node.
    Trên robot thật: dist có thể không biết tuyệt đối → chỉ cập nhật
    khi có nguồn (QR, server, hoặc trainer inject lúc sim).
    Inference thuần: trend có thể = 0 nếu không có dist.
    """

def build_state(self) -> State:
    """
    Gom từ current_node + robot.direct:
    - obstacle[N,W,E,S]  (khung map)
    - dist_goal_trend, dist_cp_trends
    - heading = self.direct
    """

def encode_state(self) -> int:
    """build_state().encode() — index vào Q-table."""
```

#### Action & vòng điều khiển

```python
def execute_action(self, action: str) -> ActionResult:
    """
    Dispatch tới Action layer. Trả ActionResult:
    - success: bool
    - moved: bool          # forward có đổi node không
    - blocked: bool        # forward đụng tường
    - new_x, new_y: int    # nếu moved
    """

def step(self) -> ActionResult:
    """
    Một bước policy đầy đủ:
    s = encode_state()
    a = get_policy(s, Q)
    return execute_action(a)
    """

def run_until_goal(self, max_steps: int) -> None:
    """Vòng lặp step() cho đến goal hoặc max_steps."""
```

### 3.3 Quy tắc hành vi (từ brainstorm + robot thật)

1. **Chỉ cập nhật obstacle hướng đang nhìn:** `direct` phải trùng hướng quét; xoay xong mới quét hướng mới.
2. **Forward = tới node kế:** Simulation nhảy tức thì; robot thật block trong `follow_line` đến `read_line() == "node"`.
3. **Rotate không đổi (x,y):** Chỉ đổi `direct`; sau rotate gọi `perceive_edge` nếu policy cần obs mới.
4. **Forward khi block:** Không đổi (x,y); `ActionResult.blocked = True`; có thể phạt reward lúc train.

### 3.4 Khác biệt Simulation vs ESP32

| Phần | Simulation | ESP32 |
|---|---|---|
| `execute_action(forward)` | Đổi tọa độ ngay | `forward_action()` + chờ node |
| `read_obstacle_ahead()` | Trainer đọc SimMap | `read_obstacle()` ultrasonic |
| `refresh_distances()` | Trainer tính từ SimMap | Tuỳ đề bài / optional |
| `Policy` | `Policy` class | `get_policy()` function |

**Interface `Robot` giữ nguyên** — chỉ implementation của `Action` và sensor khác.

---

## 4. Class `Action`

**File:** `Simulation/robot/simAction.py`, `Robot_embbed/modules/logics/action.py`

Lớp **platform-specific**, không chứa logic RL.

### 4.1 Interface

```python
class Action:
    @staticmethod
    def forward(robot: Robot, speed: int = 25) -> ActionResult: ...

    @staticmethod
    def rotate_left(robot: Robot) -> ActionResult: ...

    @staticmethod
    def rotate_right(robot: Robot) -> ActionResult: ...
```

### 4.2 `ActionResult`

```python
@dataclass
class ActionResult:
    success: bool
    moved: bool = False
    blocked: bool = False
    new_x: int | None = None
    new_y: int | None = None
```

### 4.3 Simulation — `forward`

```
1. neighbor = robot_map.get_neighbor(current_node, direct)
2. edge = robot_map.get_edge_in_direction(...)
3. if edge.isBlock or neighbor is None → blocked, không đổi x,y
4. else → robot._update_position(neighbor.x, neighbor.y); moved=True
```

### 4.4 ESP32 — `forward`

```
1. Gọi forward_action() / _follow_line
2. Loop read_line(port) đến khi "node"
3. robot._update_position(...) — tọa độ từ odometry/node counter hoặc map logic
4. Nếu timeout / lost line → success=False
```

---

## 5. Class `Node` (Robot memory)

**Cùng class `Node` với SimMap** nhưng trên RobotMap node mang thêm field perception.

**File:** `Simulation/robot/robot_map.py`; hằng số lưới `RL_lib/grid.py`

### 5.1 Thuộc tính chung (mọi map)

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `x`, `y` | `int` | Tọa độ lưới |
| `id` | `int` | `y * 10 + x` |

### 5.2 Thuộc tính chỉ dùng trên RobotMap

| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `N_obstacle` … `S_obstacle` | `0 \| 1` | Đã thấy cạnh đó bị chặn |
| `dist_goal` | `int` | Manhattan tới goal (cache) |
| `dist_checkpoint` | `list[int]` | Manhattan tới từng CP |
| `visited` | `bool` | Đã từng đứng qua (optional) |

**SimMap Node:** chỉ cần phần chung; không bắt buộc obstacle field (truth nằm trên `Edge`).

### 5.3 Phương thức

```python
def neighbor_id(direction: str) -> int: ...
def neighbor_xy(direction: str) -> tuple[int, int]: ...

def get_obstacle(direction: str) -> int:
    """0 hoặc 1. Trên SimMap có thể raise / trả 0 nếu chưa perceive."""

def set_obstacle(direction: str, value: bool, neighbor: Node | None) -> None:
    """
    Ghi obstacle hướng direction; đồng bộ ngược neighbor:
    set N trên (x,y) → set S trên (x, y+1).
    """

def perceive(direction, is_blocked, edge) -> bool:
    """
    1. Validate edge nối đúng node
    2. edge.set_block(is_blocked)   — trên RobotMap edge là bản copy memory
    3. set_obstacle(direction, is_blocked, neighbor)
    """
```

---

## 6. Class `Map` — instance `RobotMap`

**File:** `Simulation/robot/modules/robot_map.py` (tách khỏi sim)

RobotMap = `Map(width, height)` với graph `Node` + `Edge`, dùng cho memory.

### 6.1 Thuộc tính

| Thuộc tính | Kiểu |
|---|---|
| `width`, `height` | `int` |
| `nodes` | `dict[(x,y), Node]` |
| `nodes_by_id` | `dict[int, Node]` |
| `edges` | `list[Edge]` |

### 6.2 Phương thức bắt buộc

```python
def add_node(x, y) -> Node | None
def get_node(x, y) -> Node | None
def get_node_by_id(node_id) -> Node | None
def get_neighbor(node, direction) -> Node | None
def get_edge_in_direction(node, direction) -> tuple[Node|None, Edge|None]
def auto_link() -> None
    """Tạo NS_edge / WE_edge giữa node liền kề."""

def get_obstacle_at(x, y, direction) -> int:
    """
    Brainstorm: 'bỏ input hướng và vị trí → is_obstacle'.
    Implementation: node = get_node(x,y); return node.get_obstacle(direction).
    Robot gọi qua robot_map, không cần biết (x,y) nếu đã có current_node.
    """

def init_grid() -> None
    """Tạo đủ node 0..width-1, 0..height-1, auto_link, obstacle=0."""
```

### 6.3 Khởi tạo RobotMap

```
RobotMap khởi tạo rỗng obstacle (chưa biết tường).
Kích thước width×height phải khớp SimMap / bạt thật để id và neighbor đúng.
Không copy goal/checkpoint từ SimMap — robot không biết goal ở đâu (trừ khi đề cho phép).
```

---

## 7. Class `State`

**File:** `Simulation/robot/modules/state.py`, `Robot_embbed/modules/logics/state.py`

### 7.1 Thuộc tính

| Thuộc tính | Kiểu |
|---|---|
| `obstacle` | `tuple[4]` — thứ tự N,W,E,S |
| `dist_goal_trend` | `-1 \| 0 \| 1` |
| `dist_cp_trends` | `list[-1\|0\|1]` |
| `heading` | `N \| W \| E \| S` | `Robot.direct` — bắt buộc trong encode |

### 7.2 Phương thức

```python
@staticmethod
def trend(before: int, after: int) -> int:
    """after < before → +1 (gần hơn); after > before → -1; bằng → 0."""

def encode(self) -> int:
    """Công thức cố định — PC và ESP32 giống hệt nhau."""

@classmethod
def from_robot_node(cls, node: Node, prev_dist_goal, prev_dist_cp, ...) -> State: ...
```

Chi tiết encode: [ss26-strategy-RLtraining.md §2.2](./ss26-strategy-RLtraining.md).

---

## 8. Class `Policy` / `get_policy`

**File:** `Simulation/robot/modules/policy.py`, `Robot_embbed/modules/logics/policy.py`

```python
ACTIONS = ["forward", "rotate left", "rotate right"]

def get_policy(encoded_state: int, Q, actions=ACTIONS) -> str:
    """argmax Q[s]; tie-break: forward > rotate left > rotate right."""

def load_policy(path: str) -> list:
    """policy.json hoặc policy.bin."""
```

Robot **không** cập nhật Q — chỉ đọc.

---

## 9. Luồng hoàn chỉnh — robot thật

```
boot:
  robot_map = Map(W, H); robot_map.init_grid()
  Q = load_policy("policy.bin")
  robot = Robot(x0, y0, robot_map, direct="N", policy=Q)

loop:
  if ultrasonic_ready:
      robot.perceive_edge(read_obstacle())
  state = robot.build_state()
  s = state.encode()
  action = get_policy(s, Q)
  result = robot.execute_action(action)
  if result.moved:
      robot.refresh_distances(...)  # nếu có nguồn dist
  if robot.at_goal: break
```

---

## 10. Luồng hoàn chỉnh — simulation chạy policy (không train)

Giống robot thật, nhưng `read_obstacle_ahead` do harness đọc **SimMap** rồi gọi `perceive_edge`:

```
is_blocked = sim_map.read_block(robot.x, robot.y, robot.direct)
robot.perceive_edge(is_blocked)
dist_g, dist_cp = sim_map.manhattan_to_goal_cp(robot.x, robot.y)
robot.refresh_distances(dist_g, dist_cp)
```

Robot vẫn **không giữ reference** tới `sim_map` — harness làm cầu nối.

---

## 11. Mapping file hiện tại → spec

| Spec | File hiện tại | Trạng thái |
|---|---|---|
| `Robot` | `Simulation/robot/robot.py` | Khung có, thiếu `step`, `build_state`, `execute_action` |
| `Action` | `simAction.py`, `action.py` | Chưa nối `ActionResult` |
| `RobotMap` | `modules/node.py` → `RobotMap` | Gần đúng; Edge đang comment |
| `Node` (robot) | `modules/node.py` → `Node` | `perceive`, `update_obs` có |
| `State` | `modules/state.py` | Chưa implement encode |
| `Policy` | `modules/policy.py` | `get_action` có |

---

## 12. Thứ tự implement (Robot side)

1. Gộp `Node` + `Edge` + `Map` dùng chung (tách `RobotMap` instance)  
2. Hoàn thiện `State.encode` + `from_robot_node`  
3. `Robot.build_state`, `perceive_edge`, `_update_position`  
4. `Action.forward` / `rotate_*` + `ActionResult` (sim trước)  
5. `Robot.step()` nối Policy  
6. Port sensor + `Action` lên ESP32  
7. Test closed-loop: SimMap oracle + RobotMap memory + policy.json  

---

## 13. Câu hỏi cần chốt

1. Robot thật có biết tọa độ (x,y) tuyệt đối hay chỉ đếm node từ start?  
2. `dist_goal` trên robot lấy từ đâu (GPS lưới, marker, hay chỉ dùng trend lúc train)?  
3. Một lần `rotate` có tự động `perceive_edge` hay policy phải gọi riêng?  
4. Khi chưa quét hướng nào, `obstacle` mặc định `0` (giả định thông) hay `unknown` (state riêng)?  

---

*Spec: `docs/s26-strategy-Robot.md` — forward / inference và RobotMap memory.*
