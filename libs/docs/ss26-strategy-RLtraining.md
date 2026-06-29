# SS26 — Chiến lược RL Training & Inference

> Đặc tả bổ sung cho phần **forward** (`get_policy`) và **backward** (reward + học)  
> trong [SS26 Planning Nhìn công](../SS26%20Planning%20Nhìn%20công.txt).  
> Tài liệu này mô tả **concept và khung code** — chưa phải implementation.

---

## 1. Bối cảnh và mục tiêu

| Môi trường | Vai trò |
|---|---|
| **Máy tính (Simulation)** | Train Q-policy, export file policy, debug reward |
| **ESP32-S3** | Chỉ **infer**: nhận state → chọn action, không học online |

Luồng tổng thể:

```
[Train trên PC]                    [Deploy lên robot]
State → encode → Q-update    →    policy.json / policy.bin
(reward từ transition)            State → encode → get_policy → Action
```

Hai nhánh này **dùng chung**:
- Cùng `encode_state()` (công thức giống hệt PC và ESP32)
- Cùng 3 action: `forward`, `rotate left`, `rotate right`
- Cùng vector state: obstacle 4 hướng + xu hướng khoảng cách tới goal/checkpoint

---

## 2. State — đầu vào chung cho forward và backward

### 2.1 Thành phần state (đã có trong planning)

| Thành phần | Kiểu | Ghi chú |
|---|---|---|
| `obstacle[N,W,E,S]` | `0/1` × 4 | Robot memory, đồng bộ qua `Node.update_obs` |
| `dist_goal_trend` | `-1 / 0 / +1` | Xu hướng tới goal sau bước vừa rời node cũ |
| `dist_cp_trend[i]` | `-1 / 0 / +1` | **Riêng từng** checkpoint `i` — không gộp chung |
| `heading` | `N / W / E / S` | **Hướng robot đang nhìn** (`Robot.direct`) — bắt buộc trong encode |

**Lưu ý:** Giá trị khoảng cách **tuyệt đối** (`dist_goal`, `dist_checkpoint[i]`) lưu trên node/robot để **tính trend**, nhưng **không** đưa thẳng vào `encode()` — chỉ đưa các `*_trend` vào state index.

**Obstacle vs heading:** `obstacle[N,W,E,S]` theo **khung map** (Bắc luôn là N). `heading` là hướng robot. Cùng một ô obstacle nhưng robot xoay khác hướng → `forward` đi về phía khác → state khác nhau → cần cả hai trong encode.

### 2.1.1 Biến lưu khoảng cách và hàm `dist_trend`

Mỗi node (trong RobotMap) hoặc robot giữ khoảng cách Manhattan **tại node đang đứng**:

| Biến | Nơi lưu | Ý nghĩa |
|---|---|---|
| `dist_goal` | `current_node` / `Robot` | Khoảng cách node hiện tại → goal |
| `dist_checkpoint[i]` | `current_node` / `Robot` | Khoảng cách node hiện tại → checkpoint thứ `i` |

Khi robot **chuyển sang node tiếp theo** (sau `forward` thành công), so sánh khoảng cách **node cũ** (trước khi đi) với **node mới** (sau khi đến):

```
delta = dist_at_node_moi - dist_at_node_cu
trend = dist_trend(dist_at_node_cu, dist_at_node_moi)
```

Hàm `dist_trend` — nhận hai khoảng cách tuyệt đối, trả xu hướng:

| Điều kiện (`delta = sau − trước`) | Kết quả | Nghĩa |
|---|---|---|
| `delta < 0` | `+1` | **Gần hơn** (khoảng cách giảm) |
| `delta > 0` | `-1` | **Xa hơn** (khoảng cách tăng) |
| `delta == 0` | `0` | **Không đổi** |

**Luồng cập nhật (mỗi lần tới node mới):**

```
1. Trước forward: lưu snapshot
     prev_dist_goal      = current_node.dist_goal
     prev_dist_cp[i]     = current_node.dist_checkpoint[i]

2. Robot tới node mới → cập nhật (x, y), đọc khoảng cách mới
     (trainer inject từ SimMap, hoặc nguồn khác trên robot thật)

3. Tính trend đưa vào State (mỗi mục tiêu một trend riêng):
     dist_goal_trend   = dist_trend(prev_dist_goal,      current_node.dist_goal)
     dist_cp_trend[i]  = dist_trend(prev_dist_cp[i],      current_node.dist_checkpoint[i])

4. Ghi đè prev_* = giá trị hiện tại (chuẩn bị cho bước forward kế tiếp)
```

**Rotate tại chỗ:** `(x, y)` không đổi → mọi `dist_*` không đổi → mọi `*_trend = 0` (trừ khi đề bài có rule khác).

**Bước đầu episode / chưa từng forward:** chưa có node trước → mặc định mọi `*_trend = 0`.

```python
def dist_trend(dist_truoc: int, dist_sau: int) -> int:
    """
    dist_truoc: khoảng cách ở node vừa rời (node cũ).
    dist_sau:   khoảng cách ở node vừa tới (node mới).
    delta = dist_sau - dist_truoc
    """
    if dist_sau < dist_truoc:
        return +1   # gần hơn
    if dist_sau > dist_truoc:
        return -1   # xa hơn
    return 0        # không đổi
```

### 2.2 Hàm `encode_state`

**Concept:** Gộp các thành phần rời rạc thành một chỉ số nguyên `s ∈ [0, N_states)`.

**Quan trọng — mỗi checkpoint một trend riêng:**  
Không được cộng `dist_cp_trend[0] + dist_cp_trend[1] + ...` thành một số — sẽ mất xu hướng từng CP (ví dụ CP0 gần hơn nhưng CP1 xa hơn sẽ triệt tiêu nhau).  
Mỗi `dist_cp_trend[i]` là **một chữ số độc lập** trong mixed-radix (cơ số 3).

**Bước 1 — `obstacle_bits`:**

```
obstacle_bits = N×8 + W×4 + E×2 + S   →   16 giá trị (0–15)
```

**Bước 2 — pack các trend (goal + từng CP):**

Map trend `{-1, 0, +1}` → digit `{0, 1, 2}`: `digit = trend + 1`

Thứ tự cố định (ví dụ 3 checkpoint):

```
trends = [dist_goal_trend, dist_cp_trend[0], dist_cp_trend[1], dist_cp_trend[2]]
```

```
trend_packed = d₀ + d₁×3 + d₂×3² + d₃×3³
```

với `dₖ = dist_trend_k + 1` (đưa về 0..2).

**Bước 3 — `heading`:**

Hướng robot `Robot.direct` — map sang chỉ số cố định:

| `heading` | `heading_idx` |
|:---:|:---:|
| N | 0 |
| W | 1 |
| E | 2 |
| S | 3 |

**Bước 4 — ghép (thứ tự cố định):**

```
s = obstacle_bits × (3^(1 + N_cp) × 4) + trend_packed × 4 + heading_idx
```

`N_cp` = số checkpoint **trên map hiện tại** (1–3). **Q-table và `encode()` cố định `N_cp_max = 3`** — map có ít CP hơn thì slot CP thừa luôn `dist_cp_trend[i] = 0`, không cộng reward cho CP không tồn tại (xem §8).

**Số hàng Q-table (cố định theo `N_cp_max = 3`):**

```
N_rows = 16 × 3^(1 + N_cp_max) × 4
       = 16 × 3⁴ × 4
       = 5 184
```

Mọi policy export dùng **5184 hàng** dù map chỉ có 1 hoặc 2 checkpoint.

**Interface (khung code, chưa implement):**

```python
HEADING_IDX = {"N": 0, "W": 1, "E": 2, "S": 3}

class State:
  def __init__(self, obstacle, dist_goal_trend, dist_cp_trends: list, heading: str):
    """
    heading: Robot.direct — N/W/E/S, bắt buộc.
    dist_cp_trends: list độ dài N_cp_max (=3) — MỖI phần tử trend của MỘT checkpoint.
    Slot CP không có trên map: trend = 0.
    """
    ...

  def encode(self) -> int:
    """Mixed-radix: obstacle_bits + trends + heading_idx."""
    ...

  @staticmethod
  def dist_trend(dist_truoc: int, dist_sau: int) -> int:
    """delta = dist_sau - dist_truoc → +1 gần hơn, -1 xa hơn, 0 không đổi."""
    ...
```

**Nơi đặt code:** `Simulation/robot/modules/state.py` và `Robot_embbed/modules/logics/state.py` — **cùng một công thức**, chỉ khác ngôn ngữ (Python / MicroPython).

---

## 3. Forward — `get_policy` (inference trên ESP32)

### 3.1 Concept

Policy = bảng Q đã train sẵn. Inference = **argmax** trên hàng `Q[s]`:

```
action* = argmax_a Q[s, a]
```

Không cần backprop, không cần ma trận lớn lúc chạy — chỉ đọc file và so sánh 3 số.

### 3.2 Luồng trên robot (mỗi vòng lặp)

```
1. Robot đứng tại node (x, y), hướng direct
2. Cập nhật obstacle memory (sensor / quét cạnh)
3. Nếu vừa forward sang node mới: tính dist_goal_trend, dist_cp_trend[i]
   bằng dist_trend(prev_dist, current_node.dist) — mỗi CP một trend riêng
4. s = State(obstacle, trends, heading=robot.direct).encode()
5. action_name = get_policy(s, Q_table)
6. Robot.Action(action_name)  → forward / rotate left / rotate right
7. Nếu forward thành công → cập nhật (x,y); snapshot prev_dist_* cho bước sau
```

### 3.3 Module `Policy` / `get_policy`

Đã có skeleton trong:
- `Simulation/robot/modules/policy.py` → class `Policy`
- `Robot_embbed/modules/logics/policy.py` → hàm `get_policy`

**Interface thống nhất:**

```python
ACTIONS = ["forward", "rotate left", "rotate right"]

def get_policy(encoded_state: int, Q, actions=ACTIONS) -> str:
  """
  Forward pass duy nhất.
  - encoded_state: từ State.encode()
  - Q: list[list[float]] hoặc đọc từ policy.json
  - return: tên action
  """
  row = Q[encoded_state]
  best_idx = argmax(row)
  return actions[best_idx]
```

**Tie-break (đề xuất):** Nếu nhiều action cùng Q max → ưu tiên `forward` > `rotate left` > `rotate right` để robot không xoay vô hạn.

### 3.4 Export và lưu trữ policy

| File | Dùng cho | Ghi chú |
|---|---|---|
| `policy.json` | Dev, debug, học sinh xem/sửa | Human-readable |
| `policy.bin` | ESP32 production | `float32`, load nhanh, ít RAM |

**Quyết định:** Mỗi lần train xong → **`export_policy()` xuất đồng thời cả hai** (`policy.json` + `policy.bin`), cùng nội dung Q-table.

```python
def export_policy(self, json_path="policy.json", bin_path="policy.bin"):
    """Ghi cùng một Q-table ra JSON (debug) và BIN (deploy)."""
    ...
```

**ESP32:** boot đọc `policy.bin`. JSON không bắt buộc trên mạch.

Kích thước (`N_cp_max=3`): `5184 × 3 × 4` bytes ≈ **62 KB** mỗi file bin.

**Không học trên ESP32** — chỉ `read_policy()` một lần lúc boot (hoặc embed sẵn trong firmware).

### 3.5 Ràng buộc ESP32-S3

- Argmax 3 phần tử: O(1), < 1 ms
- Tránh dynamic allocation khi infer
- `encode_state` chỉ dùng phép nhân/cộng integer
- Q-table để trong Flash, không copy sang PSRAM trừ khi cần

---

## 4. Backward — Reward và hàm học (chỉ trên PC)

### 4.1 Câu hỏi: *Từ state suy ra được reward?*

**Trả lời ngắn:** Reward **không** là hàm chỉ của `state` tĩnh, mà của **transition** `(s, a, s')` — tức state trước + action + state sau.

Tuy nhiên, vì state đã encode **xu hướng khoảng cách** (`dist_*_trend`), ta có thể viết reward **dựa trên thành phần của s'** sau khi thực hiện action:

```
r = r_goal(s') + r_checkpoint(s') + r_step + r_collision(s, a) + r_success(s')
```

**Bảng reward đề xuất (có thể chỉnh khi test):**

| Sự kiện | Reward | Cách nhận biết |
|---|---|---|
| Tới goal | `+100` | `robot.at_goal()` hoặc `dist_goal == 0` |
| Đi gần goal hơn | `+10` | `dist_goal_trend == +1` trong s' |
| Đi xa goal hơn | `-5` | `dist_goal_trend == -1` |
| Qua checkpoint (lần đầu) | `+30` | `is_at_checkpoint(x,y,i)` và `cp_visited[i] == False` → đánh dấu đã qua |
| Qua lại CP đã ghé | `0` | `cp_visited[i] == True` — **chỉ tính điểm 1 lần** |
| Mỗi bước (time penalty) | `-1` | mọi step |
| Đâm tường / action invalid | `-20` | `forward` khi `obstacle[robot.direct] == 1` (tường phía trước theo heading) |
| Xoay tại chỗ (không tiến) | `-0.5` | rotate left/right |

**Checkpoint (đã chốt):** Không bắt buộc thứ tự — robot ghé CP nào trước cũng được. Trainer/Robot giữ `cp_visited: list[bool]` độ dài `N_cp` map; mỗi CP chỉ nhận reward **một lần** mỗi episode.

**Concept:** Reward shaping hướng robot về goal và checkpoint mà không cần biết toàn bộ map — chỉ cần khoảng cách cục bộ và obstacle đã biết.

### 4.2 Bellman update — Q-learning (tabular)

**Công thức:**

```
Q[s, a] ← Q[s, a] + α × (r + γ × max_a' Q[s', a'] − Q[s, a])
```

| Tham số | Gợi ý ban đầu | Ý nghĩa |
|---|---|---|
| `α` (learning rate) | `0.1` – `0.3` | Tốc độ học |
| `γ` (discount) | `0.9` – `0.99` | Coi trọng phần thưởng tương lai |
| `ε` (epsilon-greedy) | `1.0 → 0.05` | Khám phá lúc đầu, khai thác sau |

**Episode kết thúc khi:** đến goal, hết max_steps, hoặc robot kẹt.

### 4.3 Module `Trainer` (chỉ Simulation — khung code)

```python
class Trainer:
  def __init__(self, map, robot, hyperparams):
    self.Q = zeros(N_states, N_actions)
    self.alpha = hyperparams.alpha
    self.gamma = hyperparams.gamma
    self.epsilon = hyperparams.epsilon

  def select_action(self, s) -> int:
    """ε-greedy: random hoặc argmax Q[s]."""
    ...

  def compute_reward(self, s, a, s_prime, info) -> float:
    """Backward: từ transition suy ra r."""
    ...

  def update(self, s, a, r, s_prime, done):
    """Một bước Q-learning."""
    target = r if done else r + self.gamma * max(self.Q[s_prime])
    self.Q[s, a] += self.alpha * (target - self.Q[s, a])

  def run_episode(self) -> float:
    """Reset map/robot → lặp đến done → return tổng reward."""
    ...

  def train(self, n_episodes: int):
    for ep in range(n_episodes):
      self.run_episode()
      self.decay_epsilon()

  def export_policy(self, json_path="policy.json", bin_path="policy.bin"):
    """Xuất đồng thời JSON (debug) và BIN (ESP32)."""
    ...
```

**Vị trí file đề xuất:** `Simulation/robot/modules/trainer.py` (mới).

### 4.4 Luồng train một episode

```
reset robot → vị trí start, map obstacle ground truth
s = encode(state ban đầu)
loop:
  a = select_action(s)           # ε-greedy
  thực thi action trên simulation
  s' = encode(state sau action)
  r = compute_reward(s, a, s', info)
  update(s, a, r, s', done)
  s = s'
until done
```

Simulation dùng `Map` (ground truth) để tính khoảng cách thật; robot chỉ thấy obstacle qua sensor/memory — **giống robot thật**.

### 4.5 Chiến lược train (đã chốt)

**Giai đoạn 1 — Một map cố định**

- Train trên **một layout** cho đến khi robot **tới goal ổn định** (eval ε=0).
- Mục tiêu: debug pipeline `State` → `Trainer` → `export` trước khi mở rộng.

**Giai đoạn 2 — Curriculum + nhiều map**

- Bật **curriculum**: tăng dần độ khó (ít tường → nhiều tường; `N_cp` 1 → 2 → 3).
- **Nhiều map random** mỗi episode — chi tiết layout pool **config sau** (file cấu hình riêng).
- Q-table vẫn **5184 hàng** (`N_cp_max=3`); map 1–2 CP dùng slot thừa trend=0.

---

## 5. Q-table vs học trọng số (function approximation)

### 5.1 So sánh

| Tiêu chí | Q-table (tabular) | Trọng số (linear / NN) |
|---|---|---|
| Số state nhỏ (~10³) | Rất phù hợp | Overkill |
| Học trên PC | Đơn giản, dễ debug | Cần framework, nhiều hyperparameter |
| Export lên ESP32 | Lookup table, cực nhẹ | Cần infer NN — khó trên MicroPython |
| Một episode lớn | Không cần — học dần nhiều episode ngắn | Batch lớn thường ổn định hơn |
| Giải thích cho học sinh | Trực quan (bảng số) | Khó hơn |

### 5.2 Đề xuất cho SS26

**Giai đoạn 1 — Tabular Q-learning (khuyến nghị):**

- State đã được **rời rạc hoá** (obstacle bit + trend 3 mức)
- `N_states` kiểm soát được bằng số checkpoint
- Khớp code `get_policy` hiện có
- Học sinh nhìn được từng hàng Q, dễ demo

**Giai đoạn 2 — Chỉ khi state nổ:** Linear function approximation

```
Q(s, a) ≈ w_a · φ(s)
```

`φ(s)` = one-hot hoặc vector đặc trưng nhỏ (obstacle + trends). Học `w` trên PC, export vector trọng số; ESP32 tính tích vô hướng — vẫn nhẹ hơn NN đầy đủ.

**Không khuyến nghị** neural network sâu cho SS26 trừ khi map rất lớn và đã có pipeline export (TFLite / custom) — phức tạp không cần thiết cho bài toán lưới discrete.

---

## 6. Ánh xạ class trong planning ↔ module code

| Planning | Module | Forward / Backward |
|---|---|---|
| `Robot.update state` | `Robot._update_obs`, `State.encode` | Forward |
| `get_policy` | `policy.get_policy` / `Policy.get_action` | Forward |
| `Action` (3 hàm) | `simAction.Action`, `Robot_embbed/action` | Forward |
| `map` / `node` obstacle | `RobotMap`, `Node.perceive` | Forward (cập nhật state) |
| Reward + Q update | `Trainer` (mới) | Backward |
| Export policy | `Trainer.export_policy` | Backward → file cho ESP32 |

---

## 7. Thứ tự implement đề xuất

1. **Hoàn thiện `State.encode`** + `dist_*_trend` trên Simulation  
2. **`compute_reward`** + unit test vài transition tay  
3. **`Trainer`** + train thử map nhỏ 5×5  
4. **`export_policy`** → `policy.json` + `policy.bin` cùng lúc  
5. Nối `get_policy` trên Simulation với Q vừa train (closed loop)  
6. Port `encode_state` + `get_policy` + đọc `policy.bin` lên ESP32  
7. Tinh chỉnh reward nếu robot xoay tròn / không tới goal  

---

## 8. Quyết định đã chốt

| # | Chủ đề | Quyết định |
|:---:|---|---|
| 1 | **Số checkpoint** | **1–3 tùy map** (config khi load layout). Q-table / encode cố định **`N_cp_max = 3`** → `N_rows = 5 184`. Map ít CP hơn: slot CP thừa `dist_cp_trend = 0`, không reward CP ảo. |
| 2 | **Thứ tự checkpoint** | **Không bắt buộc** — chỉ cần **đi qua**. Mỗi CP **tính điểm 1 lần** / episode (`cp_visited[i]`). |
| 3 | **Train** | **Giai đoạn 1:** một map cố định đến khi chạy được. **Giai đoạn 2:** curriculum + nhiều map random — **config map pool sau**. |
| 4 | **Export** | **Đồng thời** `policy.json` (dev) **và** `policy.bin` (ESP32) mỗi lần export. |

### 8.1 Map có `N_cp` < 3 — quy tắc encode & reward

```python
N_CP_MAX = 3

# layout: checkpoints = [(x1,y1)]  → N_cp = 1
for i in range(N_CP_MAX):
    if i < len(map.checkpoints):
        dist_cp_trend[i] = dist_trend(prev_dist_cp[i], current_dist_cp[i])
    else:
        dist_cp_trend[i] = 0   # slot thừa — không có CP thật

# reward checkpoint:
if i < len(map.checkpoints) and is_at_cp(i) and not cp_visited[i]:
    r += 30
    cp_visited[i] = True
```

---

## 9. Tóm tắt trả lời hai câu hỏi trong planning

| Câu hỏi | Trả lời |
|---|---|
| Từ state suy ra được reward? | Reward từ **transition** `(s, a, s')`; state encode **trend** khoảng cách giúp tính `r` mà không cần full map trên robot |
| Q-table hay trọng số? | **Q-table** cho SS26 (state rời rạc, ESP32 lookup nhanh). Cân nhắc **linear weights** chỉ khi `N_states` vượt ~10⁴ |

---

*Tài liệu: `docs/ss26-strategy-RLtraining.md` — bổ sung cho SS26 Planning, phần forward/backward RL.*
