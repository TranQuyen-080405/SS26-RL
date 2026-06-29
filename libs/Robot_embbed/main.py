"""Boot: BLE → chờ PC kết nối → chờ Start → infer (lặp lại sau mỗi episode)."""

from modules.server.ble_monitor import (
    publish_idle,
    publish_log,
    start,
    wait_for_connection,
    wait_for_start,
)

if __name__ == "__main__":
    start()
    wait_for_connection()
    while True:
        wait_for_start()
        print("infer start")
        try:
            from modules.logics.logic import run

            run()
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
            publish_idle()
        except Exception:
            pass
