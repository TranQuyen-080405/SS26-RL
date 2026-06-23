from button import btn_onboard
from ultrasonic import ultrasonic
from utility import wait_for
from robot import robot
# from modules.logics.action import *
import time

# from button import btn_onboard
# from ultrasonic import ultrasonic
# from utility import wait_for
# from robot import robot

# import sys
# sys.path.insert(0, '/')
# from robocon_xbot import *

# import time


def run():
    print("--------------------------------------------------")
    print("SUMMER SCHOOL 2026 - ROBOT REINFORCEMENT LEARNING")
    print("--------------------------------------------------")

    # wait_for(lambda: btn_onboard.is_pressed())

    # while True:
    #     if ultrasonic.distance_cm(1) < 13:
    #         print("Obstacle detected")
    #         break
    while True:
        robot.forward(25)
    # time.sleep_ms(1000)


    # robot.forward(25,0.5)
    # forward_action()
