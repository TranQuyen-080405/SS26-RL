"""Boot: BLE → chờ PC kết nối → chờ Start → infer (lặp lại sau mỗi episode)."""

from modules.server.ble_monitor import (
    publish_idle,
    publish_log,
    set_map_cfg,
    start,
    wait_for_connection,
    wait_for_start,
)

# ---- Cấu hình map deploy (sửa ở đây) ----
MAP_CFG = {
    "w": 9,
    "h": 9,
    "start": (4, 0),
    "goal": (4, 8),
    "checkpoints": [],
    "walls": [],
}

if __name__ == "__main__":
    start()
    set_map_cfg(MAP_CFG)
    wait_for_connection()
    while True:
        wait_for_start()
        print("infer start")
        try:
            from modules.logics.logic import run

            run(MAP_CFG)
        except Exception as exc:
            print("infer crash:", exc)
            try:
                publish_log("infer CRASH: %s" % exc)
            except Exception:
                pass
            import sys

            sys.print_exception(exc)
        try:
            publish_log("Episode ket thuc — cho Start de chay lai")
        except Exception:
            pass
