# Danh sách API của các thư viện được sử dụng trong mã nguồn

Tài liệu này liệt kê chi tiết các hàm/API của các thư viện được import và thực tế sử dụng trong mã nguồn của các tệp tin trong dự án (như `robocon_xbot.py`, `raw.py`, `boot.py`, `gamepad_handler.py`, `remote_control.py`, `gamepad.py`).

---

## 1. Thư viện `robot` (`from robot import robot`)

Thư viện dùng để điều khiển hướng di chuyển, tốc độ bánh xe và các chuyển động cơ bản của robot.

### `robot.forward(speed, duration=None, brake=None)`
* **Mô tả**: Điều khiển robot di chuyển tiến về phía trước.
* **Đầu vào (Input)**:
  * `speed` (Số nguyên): Tốc độ di chuyển (0 - 100).
  * `duration` (Số thực/Số nguyên, tùy chọn): Thời gian di chuyển tính bằng giây.
  * `brake` (Boolean, tùy chọn): Trạng thái phanh sau khi hoàn thành (`True` để phanh, `False` hoặc `None` để thả trôi).
* **Đầu ra (Output)**: Không có (`None`).

### `robot.backward(speed, duration=None, brake=None)`
* **Mô tả**: Điều khiển robot di chuyển lùi về phía sau.
* **Đầu vào (Input)**:
  * `speed` (Số nguyên): Tốc độ di chuyển (0 - 100).
  * `duration` (Số thực/Số nguyên, tùy chọn): Thời gian di chuyển tính bằng giây.
  * `brake` (Boolean, tùy chọn): Trạng thái phanh sau khi hoàn thành.
* **Đầu ra (Output)**: Không có (`None`).

### `robot.turn_left(speed, duration=None)`
* **Mô tả**: Điều khiển robot rẽ (quay) sang trái.
* **Đầu vào (Input)**:
  * `speed` (Số nguyên): Tốc độ rẽ (0 - 100).
  * `duration` (Số thực/Số nguyên, tùy chọn): Thời gian rẽ tính bằng giây.
* **Đầu ra (Output)**: Không có (`None`).

### `robot.turn_right(speed, duration=None)`
* **Mô tả**: Điều khiển robot rẽ (quay) sang phải.
* **Đầu vào (Input)**:
  * `speed` (Số nguyên): Tốc độ rẽ (0 - 100).
  * `duration` (Số thực/Số nguyên, tùy chọn): Thời gian rẽ tính bằng giây.
* **Đầu ra (Output)**: Không có (`None`).

### `robot.turn_left_angle(angle)`
* **Mô tả**: Quay robot sang trái một góc chính xác chỉ định.
* **Đầu vào (Input)**:
  * `angle` (Số nguyên/Số thực): Góc quay tính bằng độ.
* **Đầu ra (Output)**: Không có (`None`).

### `robot.turn_right_angle(angle)`
* **Mô tả**: Quay robot sang phải một góc chính xác chỉ định.
* **Đầu vào (Input)**:
  * `angle` (Số nguyên/Số thực): Góc quay tính bằng độ.
* **Đầu ra (Output)**: Không có (`None`).

### `robot.set_wheel_speed(left_speed, right_speed)`
* **Mô tả**: Thiết lập tốc độ di chuyển riêng biệt cho bánh xe trái và bánh xe phải.
* **Đầu vào (Input)**:
  * `left_speed` (Số nguyên): Tốc độ bánh xe bên trái (-100 đến 100).
  * `right_speed` (Số nguyên): Tốc độ bánh xe bên phải (-100 đến 100).
* **Đầu ra (Output)**: Không có (`None`).

### `robot.stop()`
* **Mô tả**: Dừng hoạt động di chuyển của robot (tắt động cơ di chuyển).
* **Đầu vào (Input)**: Không có.
* **Đầu ra (Output)**: Không có (`None`).

### `robot.move(direction)`
* **Mô tả**: Di chuyển robot theo hướng di chuyển được chỉ định bằng mã số (thường dùng kết hợp với các nút hướng của tay cầm điều khiển).
* **Đầu vào (Input)**:
  * `direction` (Số nguyên): Mã hướng di chuyển (ví dụ: 1 đến 8 tương ứng các hướng di chuyển khác nhau).
* **Đầu ra (Output)**: Không có (`None`).

### `robot.servo_write(pin, angle)` *(Chỉ xuất hiện trong chú thích mã nguồn ví dụ)*
* **Mô tả**: Điều khiển servo kết nối thông qua lớp robot.
* **Đầu vào (Input)**:
  * `pin` (Số nguyên): Cổng/chân kết nối servo.
  * `angle` (Số nguyên): Góc quay (0 - 180 độ).
* **Đầu ra (Output)**: Không có (`None`).

---

## 2. Thư viện `motor` (`from motor import motor`)

Thư viện dùng để can thiệp và điều khiển trực tiếp các chân phần cứng của động cơ xBot.

### `motor._pin(pin, value)`
* **Mô tả**: Điều khiển mức logic hoặc độ rộng xung (PWM) trực tiếp của chân tín hiệu động cơ.
* **Đầu vào (Input)**:
  * `pin` (Số nguyên): Số thứ tự chân điều khiển trên mạch (ví dụ: 11, 12, 13, 14).
  * `value` (Số nguyên từ 0-100 hoặc Boolean): Trạng thái kích hoạt chân (`True`/`False` hoặc phần trăm xung PWM từ `0` đến `100`).
* **Đầu ra (Output)**: Không có (`None`).

---

## 3. Thư viện `servo` (`from servo import servo`)

Thư viện dùng để điều khiển góc quay của các động cơ Servo kết nối với mạch điều khiển.

### `servo.position(index, angle)`
* **Mô tả**: Điều khiển servo ở cổng chỉ định quay đến một góc xác định.
* **Đầu vào (Input)**:
  * `index` (Số nguyên): Cổng kết nối servo (ví dụ: từ 0 đến 7).
  * `angle` (Số nguyên): Góc quay của servo (từ 0 đến 180 độ).
* **Đầu ra (Output)**: Không có (`None`).

---

## 4. Thư viện `ultrasonic` (`from ultrasonic import ultrasonic`)

Thư viện tương tác với cảm biến siêu âm để đo khoảng cách.

### `ultrasonic.distance_cm(port)`
* **Mô tả**: Đo khoảng cách từ cảm biến siêu âm tới vật cản gần nhất ở phía trước.
* **Đầu vào (Input)**:
  * `port` (Số nguyên): Cổng Grove kết nối với cảm biến siêu âm (ví dụ: 1).
* **Đầu ra (Output)**: Khoảng cách đo được tính bằng centimet (cm) dưới dạng số thực (`float`).

---

## 5. Thư viện `line_array` (`from line_array import line_array`)

Thư viện tương tác với mạch cảm biến dò đường (gồm nhiều mắt đọc hồng ngoại).

### `line_array.read(port, index=None)`
* **Mô tả**: Đọc giá trị trạng thái từ cảm biến dò đường.
* **Đầu vào (Input)**:
  * `port` (Số nguyên): Cổng Grove kết nối mạch dò đường (ví dụ: 0).
  * `index` (Số nguyên, tùy chọn): Chỉ số mắt đọc cụ thể trên mạch dò đường nếu chỉ muốn đọc riêng lẻ mắt đó.
* **Đầu ra (Output)**: Trả về một tuple chứa trạng thái bật/tắt của các mắt đọc (ví dụ: `(0, 1, 1, 0)` tương ứng với phát hiện vạch đen) hoặc giá trị của mắt đọc cụ thể tại `index`.

---

## 6. Thư viện `button` (`from button import *`)

Thư viện tương tác với các nút nhấn vật lý.

### `btn_onboard.is_pressed()`
* **Mô tả**: Kiểm tra xem nút bấm tích hợp sẵn trên bo mạch (onboard button) của xBot có đang được nhấn hay không.
* **Đầu vào (Input)**: Không có.
* **Đầu ra (Output)**: Giá trị Boolean (`True` nếu nút đang được nhấn, `False` nếu không nhấn).

---

## 7. Thư viện `motion` (`from motion import motion`)

Thư viện tương tác với cảm biến gia tốc và cảm biến con quay hồi chuyển (IMU) tích hợp.

### `motion.get_accel(axis)`
* **Mô tả**: Lấy giá trị gia tốc của thiết bị theo trục chỉ định.
* **Đầu vào (Input)**:
  * `axis` (Chuỗi): Tên trục cần lấy gia tốc (`'x'`, `'y'`, hoặc `'z'`).
* **Đầu ra (Output)**: Giá trị gia tốc đo được (Số thực `float`).

### `motion.get_gyro_roll()`
* **Mô tả**: Lấy góc nghiêng bên (Roll) của thiết bị.
* **Đầu vào (Input)**: Không có.
* **Đầu ra (Output)**: Góc Roll tính bằng độ dưới dạng số thực (`float`).

### `motion.get_gyro_pitch()`
* **Mô tả**: Lấy góc nghiêng trước/sau (Pitch) của thiết bị.
* **Đầu vào (Input)**: Không có.
* **Đầu ra (Output)**: Góc Pitch tính bằng độ dưới dạng số thực (`float`).

### `motion.get_gyro_yaw()`
* **Mô tả**: Lấy góc xoay đầu (Yaw) của thiết bị.
* **Đầu vào (Input)**: Không có.
* **Đầu ra (Output)**: Góc Yaw tính bằng độ dưới dạng số thực (`float`).

### `motion.is_shaked()`
* **Mô tả**: Phát hiện xem bo mạch/robot có đang bị rung hoặc lắc mạnh hay không.
* **Đầu vào (Input)**: Không có.
* **Đầu ra (Output)**: Giá trị Boolean (`True` nếu bị lắc, `False` nếu không).

---

## 8. Thư viện cấu hình `setting` (`from setting import *`)

Thư viện cung cấp các thông số cấu hình phần cứng, cổng kết nối và phiên bản thiết bị.

### `device_config.get(key)`
* **Mô tả**: Truy vấn thông số cấu hình cụ thể của thiết bị từ đối tượng cấu hình `device_config`.
* **Đầu vào (Input)**:
  * `key` (Chuỗi): Tên thông số cấu hình (ví dụ: `'hardware_version'`).
* **Đầu ra (Output)**: Giá trị của cấu hình tương ứng (ví dụ: `1.3`).

### Các hằng số / cấu hình được gọi:
* `PORTS_DIGITAL`: Danh sách hoặc từ điển định nghĩa ánh xạ các chân tín hiệu số của các cổng mở rộng.
* `BTN_A_PIN`: Chân cắm liên kết với nút A trên mạch.
* `RGB_LED_PIN`: Chân điều khiển đèn LED màu (Neopixel) trên mạch.
* `DEV_VERSION`: Phiên bản phần cứng.
* `VERSION`: Phiên bản firmware của thiết bị.

---

## 9. Thư viện tiện ích `utility` (`from utility import *`)

Thư viện cung cấp các hàm hỗ trợ tính toán toán học và thông báo lỗi.

### `translate(value, fromMin, fromMax, toMin, toMax)`
* **Mô tả**: Chuyển đổi tỉ lệ (ánh xạ) một giá trị từ dải đo nguồn sang dải đo đích (tương tự hàm `map` trong Arduino).
* **Đầu vào (Input)**:
  * `value` (Số): Giá trị cần ánh xạ.
  * `fromMin`, `fromMax` (Số): Giới hạn dưới và giới hạn trên của dải đo nguồn.
  * `toMin`, `toMax` (Số): Giới hạn dưới và giới hạn trên của dải đo đích.
* **Đầu ra (Output)**: Giá trị sau khi được ánh xạ về dải đo mới (Số).

### `say(message)`
* **Mô tả**: Phát ra tiếng cảnh báo hoặc hiển thị/in thông điệp lỗi hoặc trạng thái kết nối lên màn hình.
* **Đầu vào (Input)**:
  * `message` (Chuỗi): Nội dung thông báo cần phát/in.
* **Đầu ra (Output)**: Không có (`None`).

### `hex_to_rgb(hex_str)`
* **Mô tả**: Chuyển đổi chuỗi mã màu dạng HEX (ví dụ `#0000ff`) sang Tuple chứa 3 giá trị màu cơ bản RGB.
* **Đầu vào (Input)**:
  * `hex_str` (Chuỗi): Chuỗi màu HEX bắt đầu bằng ký tự `#`.
* **Đầu ra (Output)**: Tuple chứa 3 số nguyên đại diện cho độ sáng các kênh `(Red, Green, Blue)` từ 0 đến 255.

---

## Các thư viện được import nhưng không gọi hàm/API trực tiếp trong mã nguồn:
* `pins` (`from pins import *`): Không có hàm nào được gọi trực tiếp.
* `led` (`from led import *`): Không có hàm nào được gọi trực tiếp.
* `speaker` (`from speaker import speaker, ...`): Chỉ được import kèm các hằng số nhạc nhưng không gọi hàm phát nhạc trực tiếp trong code đã quét.
* `led_matrix` (`from led_matrix import Image, led_matrix`): Chỉ được import nhưng không dùng đến các hàm của ma trận LED hay hình ảnh.
