"""RobotMap memory — MicroPython, hàm thuần."""

from grid import node_id, neighbor_xy, is_valid, OPPOSITE, OBSTACLE_KEYS
from rl_core import N_CP_MAX


def _empty_robot_node(x, y):
    return {
        "x": x,
        "y": y,
        "id": node_id(x, y),
        "N_obstacle": 0,
        "W_obstacle": 0,
        "E_obstacle": 0,
        "S_obstacle": 0,
        "dist_goal": 0,
        "dist_checkpoint": [0] * N_CP_MAX,
    }


def init_robot_map(width, height):
    rmap = {"width": width, "height": height, "nodes": {}}
    for y in range(height):
        for x in range(width):
            rmap["nodes"][(x, y)] = _empty_robot_node(x, y)
    return rmap


def get_node(robot_map, x, y):
    if not is_valid(x, y, robot_map["width"], robot_map["height"]):
        return None
    return robot_map["nodes"].get((x, y))


def get_obstacle_nwes(node):
    return (
        node["N_obstacle"],
        node["W_obstacle"],
        node["E_obstacle"],
        node["S_obstacle"],
    )


def set_obstacle(robot_map, x, y, direction, blocked):
    node = get_node(robot_map, x, y)
    if node is None:
        return
    val = 1 if blocked else 0
    node[OBSTACLE_KEYS[direction]] = val
    nx, ny = neighbor_xy(x, y, direction)
    neighbor = get_node(robot_map, nx, ny)
    if neighbor is not None:
        neighbor[OBSTACLE_KEYS[OPPOSITE[direction]]] = val


def perceive_edge(robot_map, x, y, direction, is_blocked):
    set_obstacle(robot_map, x, y, direction, is_blocked)


def set_distances(node, dist_goal, dist_cp_list):
    node["dist_goal"] = dist_goal
    for i in range(N_CP_MAX):
        if dist_cp_list and i < len(dist_cp_list):
            node["dist_checkpoint"][i] = dist_cp_list[i]
        else:
            node["dist_checkpoint"][i] = 0
