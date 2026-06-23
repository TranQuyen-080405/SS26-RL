import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from simAction import Action
from modules.policy import Policy
from modules.node import RobotMap

DIRECTION = ["N", "W", "E", "S"]

class Robot:
    '''
    Đặc tả Robot trong simulation:
    [Sườn của Robot này dành cho cả robot thật nhưng cần thêm các action thật]
    1. Đặc tả di chuyển (trong di chuyển cần quan tâm đến update state):
        - Di chuyển 1: đi thẳng tới node điểm theo, thì break lặp của Action để nhận lệnh tiếp theo (ngoài đời nghĩa là nhận diện được node tiếp theo)
        - Di chuyển 2: xoay 90 để xem cạnh và update obs, và lặp lại get_action để policy chọn action tiếp theo
    2. Đặc tả về hướng và nhìn thấy obstacle: 
       - Hướng nhìn của robot phải = hướng nhìn của node đó thì mới nhận được obstacle của hướng đó.
       - Nếu hướng nhìn của robot không = hướng nhìn của node đó thì không nhận được obstacle của hướng đó.
    '''
    def __init__(self, x, y, Robot_map, direct=DIRECTION[0]):
        self.x = x
        self.y = y
        self.direct = direct
        self.map = Robot_map
        self.Robot_node = Robot_map.get_node(x, y) if Robot_map else None
    
    def _update_direction(self, turn_direction): # dùng được cả trên robot với action
        if turn_direction == "left":
            self.direct = DIRECTION[(DIRECTION.index(self.direct) - 1) % 4]
        elif turn_direction == "right":
            self.direct = DIRECTION[(DIRECTION.index(self.direct) + 1) % 4]
        else:
            return
    
    def _get_direction(self):
        return self.direct

    def _update_obs(self, is_blocked):
        """Nhìn theo hướng robot, nhận is_blocked từ sensor, cập nhật robot memory."""
        if self.Robot_node is None or self.map is None:
            return

        _, edge = self.map.get_edge_in_direction(self.Robot_node, self.direct)
        self.Robot_node.perceive(self.direct, is_blocked, edge)

    def _perception(self):
        pass

    def _rotate_90(self, mode):
        match mode:
            case "left":
                # trên robot thật thêm hàm robot.turn_left_angle(90)
                self._update_direction("left")
            case "right":
                # trên robot thật thêm hàm robot.turn_right_angle(90)
                self._update_direction("right")
            case _:
                return

    def Action(self, action):
        pass
