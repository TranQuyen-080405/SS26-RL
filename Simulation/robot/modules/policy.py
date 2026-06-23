import json

Action_name = ["forward", "rotate left", "rotate right"]

class Policy:
    def __init__(self, file_path = "policy.json"):
        with open(file_path, "r") as f:
            self.Policy_matrix = json.load(f)

    def get_action(self, encoded_state, action_name=Action_name):
        """Chọn action có Q-value cao nhất.

        encoded_state: chỉ số hàng trong policy_matrix (từ State._encode_state()).
        action_names: danh sách tên action; index i khớp cột i trong Q-table.
        """

        Q = self.Policy_matrix

        if not Q or not action_name:
            print("Error: Q or names is empty")
        if encoded_state < 0 or encoded_state >= len(Q):
            print("Error: encoded_state is out of range")

        row = Q[encoded_state]

        if not row:
            print("Error: row is empty")

        best = 0
        for i in range(1, len(row)):
            if row[i] > row[best]:
                best = i

        return action_name[best]