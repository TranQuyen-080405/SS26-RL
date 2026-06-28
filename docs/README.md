# SS26-RL — Documentation index

Tài liệu **triển khai** (làm lại từ code), không phải lý thuyết chung.

## Runtime & deploy

| Doc | Nội dung |
|-----|----------|
| [ss26-robot-runtime.md](./ss26-robot-runtime.md) | ESP32: boot, infer loop, policy memoryview, action, map cố định |
| [ss26-ble-pipeline.md](./ss26-ble-pipeline.md) | BLE GATT, protocol L:/S:, Start infer, map sync PC |
| [ss26-pc-app.md](./ss26-pc-app.md) | `main.py` 3 tab, train/map/monitor |

## RL & map (spec thuật toán)

| Doc | Nội dung |
|-----|----------|
| [ss26-strategy-RLtraining.md](./ss26-strategy-RLtraining.md) | Q-learning, encode_state, reward, train |
| [s26-strategy-Robot.md](./s26-strategy-Robot.md) | RobotMap, action, inference (concept) |
| [s26-strategy-simMap.md](./s26-strategy-simMap.md) | SimMap ground truth PC |

## Phần cứng xController

| Doc | Nội dung |
|-----|----------|
| [microAPI/README.md](./microAPI/README.md) | Index microAPI |
| [microAPI/ultrasonic.md](./microAPI/ultrasonic.md) | `read_obstacle` |
| [microAPI/line_array.md](./microAPI/line_array.md) | `read_line` (TODO motor) |

## Thứ tự đọc khi sửa deploy BLE

1. `ss26-ble-pipeline.md` — protocol & map PC  
2. `ss26-robot-runtime.md` — firmware flow  
3. `ss26-pc-app.md` — tab monitor  

## Regression (tóm tắt)

- ESP32 policy = **memoryview**, không list 5184 hàng  
- BLE notify **≤240 B**, state **compact**, không walls  
- **wait_for_start** trước infer  
- MAP 10×10, start (0,0), goal (9,9) khớp PC + robot  
