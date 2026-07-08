"""Vòng chính robot — infer policy (sau wait_for_start)."""


def run(cfg):
    from modules.logics.grid import OBSTACLE_KEYS, neighbor_xy
    from modules.logics.robot_map import init_robot_map, can_move
    from modules.logics.robot_state import make_robot, inject_distances_from_map, is_at_goal, clear_obstacle_memory
    from modules.logics.policy_io import load_policy_bin, loaded_name
    from modules.logics.action import run_policy_step, set_verbose

    pump = None
    publish_state = None
    publish_log = None
    try:
        from modules.server.ble_monitor import pump, publish_idle, publish_log, publish_state, reset_wall_publish_state
    except ImportError:
        reset_wall_publish_state = None

    def _log(msg):
        print(msg)
        if publish_log:
            publish_log(msg)

    if not load_policy_bin():
        _log("SW: No valid .bin in Q_table — train on PC first")
        return
    set_verbose(False)

    w, h = cfg["w"], cfg["h"]
    s = cfg["start"]
    rmap = init_robot_map(w, h, goal=cfg["goal"], checkpoints=cfg["checkpoints"], start=s)
    bot = make_robot(s[0], s[1], "N", rmap)
    clear_obstacle_memory(bot)
    inject_distances_from_map(bot)
    if reset_wall_publish_state:
        reset_wall_publish_state(bot)
    # Reset monitor map only when a new START begins.
    if publish_idle:
        try:
            publish_idle(bot)
        except Exception:
            pass

    step = 0
    _log("Inference | policy=%s | map=%dx%d start=%s goal=%s" % (loaded_name(), w, h, s, cfg["goal"]))
    _log("step   pos       dir      s  action")
    if publish_state:
        publish_state(bot, phase="r", step=0)
    if pump:
        pump(50)

    # Lazy import — dùng trong loop, nhưng import một lần ở đầu
    is_stopped = None
    _stop = None
    try:
        from modules.server.ble_monitor import is_stopped
        from modules.logics.action import _stop
    except ImportError:
        pass

    seen_walls = set()

    def _wall_signature(x, y, d):
        nx, ny = neighbor_xy(x, y, d)
        if (x, y) <= (nx, ny):
            return (x, y, nx, ny)
        return (nx, ny, x, y)

    def _collect_seen_walls():
        out = set()
        nodes = bot.get("robot_map", {}).get("nodes") or {}
        for (x, y), node in nodes.items():
            for d in ("N", "W", "E", "S"):
                if node.get(OBSTACLE_KEYS[d], 0) and can_move(bot["robot_map"], x, y, d) is False:
                    out.add(_wall_signature(x, y, d))
        return out

    end_status = "stopped"
    while True:
        if is_stopped and is_stopped():
            end_status = "stopped"
            if publish_state:
                publish_state(bot, phase="s", step=step)
            if _stop:
                _stop()
            break

        if is_at_goal(bot):
            end_status = "goal"
            if publish_state:
                publish_state(bot, phase="g", step=step)
            break

        step += 1
        try:
            action, result, state_s, sensor_wall = run_policy_step(bot)
        except Exception as exc:
            _log("SW: Step %d Exception: %s" % (step, exc))
            if publish_state:
                publish_state(bot, phase="c", step=step)
            end_status = "collision"
            break

        if publish_state:
            publish_state(bot, phase="r", step=step, action=action)
        _log(
            "%-5d  (%d,%d)   %-3s  %5d  %-14s"
            % (step, bot["x"], bot["y"], bot["direct"], state_s, action)
        )
        if sensor_wall:
            seen_walls = _collect_seen_walls()
            _log("Sensor: wall detected (%d edges seen)" % len(seen_walls))
        if result.get("collision"):
            end_status = "collision"
            if publish_state:
                publish_state(bot, phase="c", step=step, action=action)
            break
        if pump:
            pump(80)

    if end_status in ("goal", "collision"):
        if not seen_walls:
            seen_walls = _collect_seen_walls()
        node_visits = bot.get("node_visits") or {}
        # MicroPython dict_view không hỗ trợ len(dict.keys()).
        unique_cells = len(node_visits) if isinstance(node_visits, dict) else 0
        moved_new_cells = max(0, unique_cells - 1)
        cp_visited = bot.get("cp_visited") or []
        cp_count = sum(1 for v in cp_visited if v)
        _log("Result: %s | steps=%d" % (end_status, step))
        _log("Stats: walls_seen=%d | new_cells=%d | checkpoints=%d" % (len(seen_walls), moved_new_cells, cp_count))
    elif end_status == "stopped":
        _log("Result: stopped | steps=%d" % step)
    _log("SW: Episode finished. Waiting for new Start command...")
    if end_status in ("goal", "collision"):
        try:
            publish_idle(bot)
        except Exception:
            pass
