"""Boot: BLE → chờ PC kết nối → chờ Start → infer."""

from modules.server.ble_monitor import start, wait_for_connection, wait_for_start

if __name__ == "__main__":
    start()
    wait_for_connection()
    wait_for_start()
    print("infer start")
    try:
        from modules.logics.logic import run

        run()
    except Exception as exc:
        print("infer crash:", exc)
        try:
            from modules.server.ble_monitor import publish_log

            publish_log("infer CRASH: %s" % exc)
        except Exception:
            pass
        import sys

        sys.print_exception(exc)
