# btn_onboard — Onboard Button

Chức năng chính và chức năng của btn_onboard

## Function

### `btn_onboard.is_pressed()`

Lấy giá trị hiện tại của nút nhấn trên board. Kết quả trả về là True khi nút được nhấn, hoặc là False khi nút không được nhấn.

## Sample Code

```python
while True:
    if btn_onboard.is_pressed():
        print("Button Onboard is pressed")
```
