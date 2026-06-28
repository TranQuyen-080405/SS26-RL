# SS26 — BLE pipeline (Robot ↔ PC Monitor)

> Spec triển khai: kết nối, Start infer, đồng bộ map/log. Làm lại từ doc này + `ss26-robot-runtime.md`.

---

## 1. Kiến trúc

```
┌──────────────────── ESP32 ────────────────────┐
│ main.py → wait_* → makeRobot.run               │
│ ble_monitor.py                                │
│   RX (write)  ←── PC Start                    │
│   TX (notify) ──→ PC log + state              │
└───────────────────────────────────────────────┘
                      BLE (Nordic UART)
┌──────────────────── PC ───────────────────────┐
│ main.py tab "Robot Monitor" (bleak)           │
│   scan → connect → start_notify(TX)           │
│   write_gatt_char(RX, b"S") on Start infer    │
└───────────────────────────────────────────────┘
```

PC app thống nhất: `main.py` (3 tab). Tab monitor = code cũ `robot_monitor.py`.

---

## 2. GATT (MicroPython `bluetooth.BLE`)

| | UUID | Properties |
|---|------|------------|
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | Nordic UART |
| TX (robot → PC) | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | read, **notify** |
| RX (PC → robot) | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | write, write-without-response |

Advertising: local name `"Robot"` + service UUID trong adv packet.

**PC (bleak):** tìm TX/RX theo UUID trên; fallback scan characteristic notify+write trong service không phải 1800/1801.

---

## 3. Framing dòng (TX notify)

Mỗi notify = **một dòng** text UTF-8 + `\n` (robot ghép sẵn).

| Prefix | Ý nghĩa | Ví dụ |
|--------|---------|--------|
| `L:` | Log / sự kiện | `L:step 3 \| (1,0) N \| forward` |
| `S:` | State JSON compact | `S:{"x":1,"y":0,"d":"E","p":"r","n":3,"a":"forward"}` |

PC buffer `_tx_buf`, split theo `\n`, parse từng dòng.

**Giới hạn:** `_MAX_NOTIFY = 240` byte/dòng (cắt nếu dài hơn).  
→ **Không gửi** `walls` array (~500+ byte). PC tự vẽ tường biên.

---

## 4. JSON state compact (robot → PC)

Hàm: `ble_monitor._compact_state(robot, phase, step, action)`.

| Field | Kiểu | Bắt buộc | Mô tả |
|-------|------|----------|--------|
| `x` | int | ✓ | Cột robot |
| `y` | int | ✓ | Hàng robot |
| `d` | str | ✓ | `N`/`W`/`E`/`S` — `robot["direct"]` |
| `p` | str | ✓ | Phase (bảng dưới) |
| `n` | int | khi step>0 | Số bước infer |
| `a` | str | tùy | Action vừa chọn: `forward`, `rotate left`, `rotate right` |

**Phase `p`:**

| Giá trị | Nghĩa | Khi gửi |
|---------|--------|---------|
| `i` | Idle, chờ Start | `publish_idle`, reconnect |
| `r` | Đang infer | Mỗi bước + đầu vòng (`step=0` không có `n`) |
| `g` | Tới goal | `is_at_goal` |
| `c` | Collision / lỗi | `result["collision"]` hoặc exception |

Ví dụ idle: `S:{"x":0,"y":0,"d":"N","p":"i"}`  
Ví dụ bước 2: `S:{"x":0,"y":1,"d":"N","p":"r","n":2,"a":"forward"}`

`_publish_json_state`: bỏ qua gửi nếu `len("S:"+json+"\n") > 240`.

---

## 5. RX — Start infer (PC → robot)

PC: `await client.write_gatt_char(rx_char, b"S", response=False)`

Robot IRQ `_IRQ_GATTS_WRITE` → `_on_rx(data)`:

```
data[0:1] == b"S"           → _start_flag = True, publish_log("RX START (PC)")
data.strip().upper() in (b"S", b"START")  → tương tự
```

`wait_for_start()` thoát khi `_start_flag`; sau đó `makeRobot.run()`.

Nút onboard: `btn_onboard.is_pressed()` cũng set start (không qua RX).

---

## 6. Luồng thời gian (happy path)

```
Robot boot
  start()                    # advertise
  wait_for_connection()      # block
PC  Quét BLE → Kết nối
  IRQ connect
  publish_idle()             → S: p=i
PC  start_notify(TX)
PC  reset map (0,0) N idle

PC  Start infer → RX "S"
  publish_log RX START (PC)
  _start_flag = True
  wait_for_start exits
  publish_log START OK — infer begin

  makeRobot.run()
  publish_log infer loop — policy loaded
  publish_state p=r step=0
  loop:
    run_policy_step
    publish_state p=r n=step a=action
    publish_log step N | ...
PC  _on_tx_notify → map + path + Infer: đang chạy

Goal → S: p=g, L:GOAL
```

Mất BLE giữa chừng: robot `wait_for_start` logic reconnect; infer đang chạy thì notify fail im lặng (`OSError` pass).

---

## 7. PC — map model (tab Robot Monitor)

File: `main.py` — class `MonitorMapModel`.

**Khung cố định** (khớp `makeRobot.py`):

```python
MAP_W, MAP_H = 10, 10
MAP_START = (0, 0)
MAP_GOAL = (9, 9)
```

Khởi tạo: `apply_boundary_walls` local (giống `robot_map.apply_boundary_walls`).

**`apply_ble(msg)`** — merge, không rebuild từ `w/h/start/goal` BLE:

- Luôn cập nhật `x,y,d` nếu có key
- `p,n,a` → phase, step, last_action
- `walls` (nếu có tương lai): merge lên boundary; hiện robot **không** gửi

**Path:** mỗi state mới, nếu `(x,y)` đổi → append path. Bước infer đầu (`p=r`, `n=1`) reset path về start.

**UI trạng thái infer:** `infer_var` — Idle / đang gửi / đang chạy / GOAL / collision.  
Trigger từ `S.p` và log `START OK`, `infer loop`, `GOAL`.

---

## 8. PC — BLE thread (`RobotMonitorApp`)

- Thread daemon: `asyncio.run(_ble_loop())`
- Connect: `BleakClient` + `_wait_io_gatt` (retry, Windows uncached GATT)
- Loop 150ms: nếu `_start_infer_event` → `_send_start(client)`
- `_on_tx_notify`: parse → `root.after(0, ...)` (thread-safe Tk)
- Disconnect: `_stop_ble.set()`, join thread

Dependency: `pip install bleak`

---

## 9. Log kỳ vọng trên PC (terminal monitor)

```
Ket noi MAC: xx:xx:...
RX START (PC)
START OK — infer begin
infer loop — policy loaded
step 1 | (0,0) N | rotate right
step 2 | (0,0) W | forward
...
GOAL — tới đích
```

Nếu dừng sau `infer loop — policy loaded`: thường là **OOM policy** (đã fix memoryview) hoặc exception bước 1 — xem `step N ERROR` / `infer CRASH`.

---

## 10. Làm lại từ đầu — checklist

### Robot

1. `ble_monitor.start()` — UART GATT, không max_len 512  
2. Block `wait_for_connection` + `wait_for_start`  
3. `makeRobot` + `policy_io` memoryview  
4. Mỗi bước: `publish_state` compact + `publish_log`  
5. `pump(ms)` giữa các bước infer  

### PC

1. bleak central, UUID TX/RX  
2. `MonitorMapModel` 10×10 + boundary  
3. Parse `L:` / `S:` theo dòng  
4. Nút Start → write `b"S"`  
5. Hiển thị phase + path  

### Không làm

- Gửi full walls mỗi notify  
- Load Q-table dạng list trên ESP32  
- Auto-infer trước Start  
- Dùng hai stack BLE cùng lúc trên xController  

---

*Cập nhật theo `Robot_embbed/modules/server/ble_monitor.py` + `main.py` (PC).*
