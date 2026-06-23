import json

# Q-table: policy_matrix[state][action]
# policy_matrix = []

action_name = ["forward", "rotate left", "rotate right"]

def read_policy(file_path="policy.json"):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception:
        return []

#----------------------------------------------------------------------

def get_policy(encoded_state, action_name = action_name, Q = []):
    """Chọn action có Q-value cao nhất.

    encoded_state: chỉ số hàng trong policy_matrix (từ State._encode_state()).
    action_names: danh sách tên action; index i khớp cột i trong Q-table.
    """

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

