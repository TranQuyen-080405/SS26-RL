"""Vòng chính robot — infer policy (sau wait_for_start)."""


def run(cfg):
    from modules.logics.robot_map import init_robot_map, apply_walls_from_spec
    from modules.logics.robot_state import make_robot, inject_distances_from_map, is_at_goal, clear_obstacle_memory
    from modules.logics.policy_io import load_policy_bin, loaded_name
    from modules.logics.action import run_policy_step

    pump = None
    publish_state = None
    publish_log = None
    try:
        from modules.server.ble_monitor import pump, publish_idle, publish_log, publish_state
    except ImportError:
        pass

    def _log(msg):
        print(msg)
        if publish_log:
            publish_log(msg)

    print("--------------------------------------------------")
    print("SUMMER SCHOOL 2026 - ROBOT REINFORCEMENT LEARNING")
    print("--------------------------------------------------")

    _log("SW: Scanning Q_table for .bin...")
    if not load_policy_bin():
        _log("SW: No valid .bin in Q_table — train on PC first")
        return
    _log("SW: Loaded: %s" % loaded_name())

    w, h = cfg["w"], cfg["h"]
    s = cfg["start"]
    _log("SW: Initializing local robot map %dx%d starting at %s" % (w, h, s))
    rmap = init_robot_map(w, h, goal=cfg["goal"], checkpoints=cfg["checkpoints"], start=s)
    apply_walls_from_spec(rmap, cfg["walls"])
    bot = make_robot(s[0], s[1], "N", rmap)
    clear_obstacle_memory(bot)
    inject_distances_from_map(bot)

    step = 0
    _log("SW: Inference loop started - policy loaded")
    if publish_state:
        publish_state(bot, phase="r", step=0)
    if pump:
        pump(50)

    while True:
        from modules.server.ble_monitor import is_stopped
        if is_stopped():
            _log("SW: Stop signal received from PC. Stopping robot...")
            from modules.logics.action import _stop
            _stop()
            break

        if is_at_goal(bot):
            _log("SW: GOAL reached at (%d,%d)" % (bot["x"], bot["y"]))
            if publish_state:
                publish_state(bot, phase="g", step=step)
            break

        step += 1
        try:
            action, result = run_policy_step(bot)
        except Exception as exc:
            _log("SW: Step %d Exception: %s" % (step, exc))
            if publish_state:
                publish_state(bot, phase="c", step=step)
            break

        if publish_state:
            publish_state(bot, phase="r", step=step, action=action)
        _log(
            "SW: Step %d | Robot state: (%d,%d) %s | Chosen action: %s%s"
            % (
                step,
                bot["x"],
                bot["y"],
                bot["direct"],
                action,
                " | COLLISION!" if result.get("collision") else "",
            )
        )
        if result.get("collision"):
            if publish_state:
                publish_state(bot, phase="c", step=step, action=action)
            break
        if pump:
            pump(80)

    _log("SW: Episode finished. Waiting for new Start command...")
    try:
        publish_idle()
    except Exception:
        pass
