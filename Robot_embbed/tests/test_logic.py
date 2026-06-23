import time

_distance = 30


def testLogic():
    print("--------------------------------------------------")
    print("SUMMER SCHOOL 2026 - ROBOT REINFORCEMENT LEARNING")
    print("--------------------------------------------------")
    print("Button pressed (mock)")

    global _distance
    _distance = 30

    # while True:
    #     if _distance < 13:
    #         print("Obstacle detected")
    #         break
    #     print(f"Forward, distance={_distance}cm")
    #     time.sleep(0.05)
    #     _distance -= 1
    
    for count in range(10000):
        print(count)

    print("Robot stopped (mock)")
