"""Vòng chính robot — infer policy (sau wait_for_start)."""

MAP_W = 10
MAP_H = 10
START = (0, 0)
GOAL = (MAP_W - 1, MAP_H - 1)
CHECKPOINTS = []


def run():
    from modules.logics.robot_map import init_robot_map
    from modules.logics.robot_state import make_robot, inject_distances_from_map, is_at_goal
    from modules.logics.policy_io import load_policy_bin
    from modules.logics.action import run_policy_step

    pump = None
    publish_state = None
    publish_log = None
    try:
        from modules.server.ble_monitor import pump, publish_state, publish_log
    except ImportError:
        pass

    def _log(msg):
        print(msg)
        if publish_log:
            publish_log(msg)

    print("--------------------------------------------------")
    print("SUMMER SCHOOL 2026 - ROBOT REINFORCEMENT LEARNING")
    print("--------------------------------------------------")

    if not load_policy_bin("modules/logics/Q_table/policy.bin"):
        _log("policy.bin not found or wrong size — train on PC first")
        return

    rmap = init_robot_map(
        MAP_W, MAP_H, goal=GOAL, checkpoints=CHECKPOINTS, start=START
    )
    bot = make_robot(START[0], START[1], "N", rmap)
    inject_distances_from_map(bot)

    step = 0
    _log("infer loop — policy loaded")
    if publish_state:
        publish_state(bot, phase="r", step=0)
    if pump:
        pump(50)

    while True:
        if is_at_goal(bot):
            _log("GOAL — tới đích")
            if publish_state:
                publish_state(bot, phase="g", step=step)
            break

        step += 1
        try:
            action, result = run_policy_step(bot)
        except Exception as exc:
            _log("step %d ERROR: %s" % (step, exc))
            if publish_state:
                publish_state(bot, phase="c", step=step)
            break

        if publish_state:
            publish_state(bot, phase="r", step=step, action=action)
        _log(
            "step %d | (%d,%d) %s | %s%s"
            % (
                step,
                bot["x"],
                bot["y"],
                bot["direct"],
                action,
                " COLLISION" if result.get("collision") else "",
            )
        )
        if result.get("collision"):
            if publish_state:
                publish_state(bot, phase="c", step=step, action=action)
            break
        if pump:
            pump(80)
