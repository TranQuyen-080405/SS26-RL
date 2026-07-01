import machine, time

# support libs
from setting import *
from utility import *

# hardware libs
from pins import *
from led import *
from speaker import speaker, BIRTHDAY, TWINKLE, JINGLE_BELLS, WHEELS_ON_BUS, FUR_ELISE, CHASE, JUMP_UP, JUMP_DOWN, POWER_UP, POWER_DOWN
from ultrasonic import ultrasonic
from line_array import line_array
from button import *
from motor import motor
from servo import servo
from led_matrix import Image, led_matrix
from motion import motion
from robot import robot

# wireless libs
from ble import ble_o, ble
#from wifi import *

STOP = const(0)
BRAKE = const(1)

def stop_xbot(then=STOP):
    if then == STOP:
        robot.stop()
    elif then == BRAKE:
        if device_config.get('hardware_version') == 1.3:
            motor._pin(11, 100)
            motor._pin(12, 100)
            motor._pin(13, 100)
            motor._pin(14, 100)
        else:
            motor._pin(11, True)
            motor._pin(12, True)
            motor._pin(13, True)
            motor._pin(14, True)
        time.sleep_ms(150)
        robot.stop()
    else:
        return

speed_factors = [ 
    [1, 1], [0.7, 1], [0, 1], [-0.5, 0.5], 
    [-2/3, -2/3], [0, 1], [-0.5, 0.5], [-0.7, 0.7] 
] 
#0: forward, 1: light turn, 2: normal turn, 3: heavy turn, 4:  backward, 5: strong light turn, 6: strong normal turn, 7: strong heavy turn
            
m_dir = -1 #no found
i_lr = 0 #0 for left, 1 for right
t_finding_point = time.time_ns()
servo_current_position = [0, 0, 0, 0, 0, 0, 0, 0]
robocon_servos_pos = {}

def follow_line(speed, port, now=None, backward=True):
    global m_dir, i_lr, t_finding_point
    if now == None:
        now = line_array.read(port)

    if now == (0, 0, 0, 0):
        #no line found
        if backward:
            robot.backward(int(speed*0.7))
    else:
        if (now[1], now[2]) == (1, 1):
            if m_dir == 0:
                robot.set_wheel_speed(speed, speed) #if it is running straight before then robot should speed up now           
            else:
                m_dir = 0 #forward
                robot.set_wheel_speed(speed * 0.7, speed * 0.7) #just turn before, shouldn't set high speed immediately, speed up slowly
        else:
            if (now[0], now[1]) == (1, 1): 
                m_dir = 2 #left normal turn
                i_lr = 0
            elif (now[2], now[3]) == (1, 1): 
                m_dir = 2 #right normal turn
                i_lr = 1
            elif now == (1, 0, 1, 0): 
                if m_dir != -1:
                    m_dir = 1
                    i_lr = 0
            elif now == (0, 1, 0, 1): 
                if m_dir != -1:
                    m_dir = 1
                    i_lr = 1
            elif now == (1, 0, 0, 1): 
                if m_dir != -1:
                    m_dir = 0
                    i_lr = 0
            elif now[1] == 1: 
                m_dir = 1 #left light turn
                i_lr = 0
            elif now[2] == 1:
                m_dir = 1 #right light turn
                i_lr = 1
            elif now[0] == 1: 
                m_dir = 3 #left heavy turn
                i_lr = 0
            elif now[3] == 1: 
                m_dir = 3 #right heavy turn
                i_lr = 1

            #print(m_dir)
            left_speed = speed * speed_factors[m_dir][i_lr]
            if left_speed < 0 and left_speed > -30:
                left_speed = -30
            if left_speed > 0 and left_speed < 30:
                left_speed = 30
            right_speed = speed * speed_factors[m_dir][1-i_lr]
            if right_speed < 0 and right_speed > -30:
                right_speed = -30
            if right_speed > 0 and right_speed < 30:
                right_speed = 30

            robot.set_wheel_speed(left_speed, right_speed)

            if m_dir == 3:
                while now[1] != 1 and now[2] != 1:
                    time.sleep_ms(20)
                    now = line_array.read(port)

def follow_line_until_end(speed, port, timeout=10000, then=STOP):
    count = 3
    last_time = time.ticks_ms()

    while time.ticks_ms() - last_time < timeout:
        sleep_time = 20
        now = line_array.read(port)

        if now == (0, 0, 0, 0):
            count = count - 1
            if count == 0:
                break
            speed = int(speed/2) # slow down when end condition met
            if speed < 30:
                speed = 30
            sleep_time = sleep_time + 10

        if speed >= 0:
            follow_line(speed, port, now, False)
        else:
            robot.backward(abs(speed))

        time.sleep_ms(sleep_time)

    stop_xbot(then)

def follow_line_until_cross(speed, port, timeout=20000, then=STOP):
    status = 1
    count = 0
    last_time = time.ticks_ms()

    while time.ticks_ms() - last_time < timeout:
        now = line_array.read(port)
        adjust_speed = speed

        if status == 1:
            if now != (1, 1, 1, 1):
                status = 2
        elif status == 2:
            if now == (1, 1, 1, 1):
                count = count + 1
                if count == 4:
                    break
                adjust_speed = int(speed/2) # slow down when end condition met
                if speed < 30:
                    speed = 30
            else:
                adjust_speed = speed

        if speed >= 0:
            follow_line(adjust_speed, port, now)
        else:
            robot.backward(abs(speed))

        time.sleep_ms(10)

    robot.forward(speed, 0.1)
    stop_xbot(then)

def follow_line_until(speed, condition, port, timeout=20000, then=STOP):
    status = 1
    count = 0
    last_time = time.ticks_ms()

    while time.ticks_ms() - last_time < timeout:
        now = line_array.read(port)

        if status == 1:
            if now != (1, 1, 1, 1):
                status = 2
        elif status == 2:
            if condition():
                count = count + 1
                if count == 3:
                    break

        if speed >= 0:
            follow_line(speed, port)
        else:
            robot.backward(abs(speed))

        time.sleep_ms(10)

    stop_xbot(then)

def turn_until_line_detected(m1_speed, m2_speed, port, timeout=5000, then=STOP):
    counter = 0
    status = 0
  
    last_time = time.ticks_ms()

    robot.set_wheel_speed(m1_speed, m2_speed)

    while time.ticks_ms() - last_time < timeout:
        line_status = line_array.read(port)

        if status == 0:
            if line_status == (0, 0, 0, 0): # no black line detected
                # ignore case when robot is still on black line since started turning
                status = 1
        
        elif status == 1:
            robot.set_wheel_speed(m1_speed, m2_speed)
            status = 2
            counter = 4
        elif status == 2:
            if line_status[0] == 1 or line_status[1] == 1 or line_status[2] == 1 or line_status[3] == 1:
                robot.set_wheel_speed(int(m1_speed*0.75), int(m2_speed*0.75))
                counter = counter - 1
                if counter <= 0:
                    break

        time.sleep_ms(10)

    stop_xbot(then)

def turn_until_condition(m1_speed, m2_speed, condition, timeout=5000):
    count = 0

    robot.set_wheel_speed(m1_speed, m2_speed)

    last_time = time.ticks_ms()

    while time.ticks_ms() - last_time < timeout:
        if condition():
            count = count + 1
            if count == 3:
                break
        time.sleep_ms(10)

    robot.stop()

def ball_launcher(servo_1=0, servo_2=1, mode=-1):
    if mode == 1:
        servo.position(servo_1, 180)
    if mode == 0:
        servo.position(servo_1, 180)
        time.sleep_ms(250)
        servo.position(servo_2, 180)
        time.sleep_ms(250)
        servo.position(servo_1, 90)
        time.sleep_ms(250)
        servo.position(servo_2, 20)
        time.sleep_ms(250)

def set_servo(index, angle):
    global servo_current_position, robocon_servos_pos    
    servo.position(index, angle)
    robocon_servos_pos[index] = angle

def set_servo_position(pin, next_position, speed=70):
    global servo_current_position, robocon_servos_pos
    if speed < 0:
        speed = 0
    elif speed > 100:
        speed = 100
    
    sleep = int(translate(speed, 0, 100, 40, 0))

    if pin in robocon_servos_pos:
        current_position = robocon_servos_pos[pin]
    else:
        current_position = 0
        set_servo(pin, 0) # first time control

    if next_position < current_position:
        for i in range(current_position, next_position, -1):
            set_servo(pin, i)
            time.sleep_ms(sleep)
    else:
        for i in range(current_position, next_position):
            set_servo(pin, i)
            time.sleep_ms(sleep)


def move_servo_position(pin, angle):
    global servo_current_position, robocon_servos_pos
    
    if pin in robocon_servos_pos:
        current_position = robocon_servos_pos[pin]
    else:
        current_position = 0
        
    next_position = current_position + angle
    
    if next_position < 0:
        next_position = 0
    if next_position > 180:
        next_position = 180
    set_servo(pin, next_position)




