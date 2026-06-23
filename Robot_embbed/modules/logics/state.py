

class State:
    def __init__(self, state, pos, yaw, new_yaw, isObstacle, goal, checkpoints, isgoal):
        self.state = state
        self.pos = pos
        self.yaw = yaw
        self.new_yaw = new_yaw
        self.isObstacle = isObstacle
        self.goal = goal
        self.checkpoints = checkpoints
        self.isgoal = isgoal

    def yaw_update(self):
        # TODO: Update yaw
        self.yaw = self.new_yaw
        return self.yaw

    def _encode_state(self):
        # TODO: lấy các yếu tố trong state và encode thành state thật trong ma trận.
        self.state = 0
        return 0

    def state_update(self):
        # TODO: gọi hàm _encode_state để encode state thật trong ma trận, và sau đó cập nhật
        pass
