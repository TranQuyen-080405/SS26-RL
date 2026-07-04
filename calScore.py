import os
import sys

# =====================================================================
# Cấu hình file policy mặc định (Bạn có thể sửa trực tiếp tên hoặc path ở đây)
# Hoặc truyền qua đối số khi chạy: python calScore.py <tên_hoặc_đường_dẫn_policy>
# =====================================================================
POLICY_FILE = "policy.bin"

if len(sys.argv) > 1:
    POLICY_FILE = sys.argv[1]

# 1. Thiết lập sys.path để import thư viện hệ thống
_LIBS = os.path.abspath(os.path.join(os.path.dirname(__file__), "libs"))
if _LIBS not in sys.path:
    sys.path.insert(0, _LIBS)

from bootstrap import setup_paths
setup_paths()

from map.map_io import list_map_files, build_sim_map_from_file
from Simulation.rl_runner import load_policy_for_infer, _robot_map_from_sim, _reset_at_start, _episode_at_goal, MAX_STEPS_INFER
from robot import robot as rb
from robot import action as act

def calculate_map_score(sim_map, q_table, policy_name, map_name):
    # Khởi tạo trạng thái robot và bản đồ mô phỏng
    rmap = _robot_map_from_sim(sim_map)
    bot = rb.make_robot(sim_map["start"][0], sim_map["start"][1], "N", rmap)
    _reset_at_start(bot, sim_map)

    # Ghi nhận các checkpoint đã đi qua (bao gồm cả điểm bắt đầu nếu trùng)
    visited_cps = set()
    if (bot["x"], bot["y"]) in sim_map.get("checkpoints", []):
        visited_cps.add((bot["x"], bot["y"]))

    max_steps = MAX_STEPS_INFER
    collision_occurred = False
    goal_reached = False
    step_count = 0

    for step in range(1, max_steps + 1):
        if _episode_at_goal(bot, sim_map):
            goal_reached = True
            step_count = step - 1
            break

        # Lấy trạng thái mã hóa và hành vi từ Q-table
        s = rb.build_encoded_state(bot)
        from RL_lib.rl_core import get_policy
        a_name = get_policy(s, q_table)

        # Thực thi hành động trên mô phỏng
        result = act.execute_action_sim(bot, sim_map, a_name)
        step_count = step

        # Cập nhật checkpoint đã đi qua sau bước di chuyển
        curr_pos = (bot["x"], bot["y"])
        if curr_pos in sim_map.get("checkpoints", []):
            visited_cps.add(curr_pos)

        if result.get("collision"):
            collision_occurred = True
            break

        if _episode_at_goal(bot, sim_map):
            goal_reached = True
            break

    # --- TÍNH ĐIỂM ---
    score = 0
    # 1. Chạm goal + 400 điểm
    if goal_reached:
        score += 400
    # 2. Chạm checkpoint: mỗi checkpoint + 100 điểm
    score += 100 * len(visited_cps)
    # 3. Chạm collision - 100 điểm
    if collision_occurred:
        score -= 100
    # 4. Mỗi action (forward/rotate) - 2 điểm
    score -= 2 * step_count

    return score

def main():
    # Nạp policy
    q, policy_path = load_policy_for_infer(POLICY_FILE)
    if not q:
        print(f"Error: Không tìm thấy policy file '{POLICY_FILE}'!")
        return

    # Liệt kê tất cả các bản đồ inference
    infer_paths = list_map_files("infer")
    if not infer_paths:
        print("Không tìm thấy bản đồ nào trong thư mục map/infer/")
        return

    total_score = 0
    for path in infer_paths:
        sim_map = build_sim_map_from_file(path)
        base_name = os.path.basename(path)
        map_name = base_name.replace("map_infer_", "").replace(".json", "")
        
        map_score = calculate_map_score(sim_map, q, os.path.basename(policy_path), map_name)
        total_score += map_score
        
        # In tên map và điểm số
        print(f"map {map_name}: {map_score}")

    print("=" * 46)
    print(f"Total Score:   {total_score}")
    print("=" * 46)

if __name__ == "__main__":
    main()
