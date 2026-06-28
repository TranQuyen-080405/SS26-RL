"""PC test — mock log server (không dùng WiFi/HTML cũ trên robot)."""

import os
import sys
import socket
import json
import time
import threading

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_TESTS = os.path.dirname(os.path.abspath(__file__))
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)

from test_logic import testLogic

MAX_LOG_LINES = 1000
_logs = []
_installed = False
_shutting_down = False

_INDEX_HTML = b"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Log</title></head>
<body style="background:#111;color:#ccc;font-family:monospace;padding:12px">
<pre id="out"></pre>
<script>
async function poll(){try{const r=await fetch('/api/log');const lines=await r.json();
document.getElementById('out').textContent=lines.join('\\n');}catch(e){}}
setInterval(poll,500);poll();
</script></body></html>"""


def install_print():
    global _installed
    if _installed:
        return
    _installed = True
    import builtins

    _orig = builtins.print

    def _print(*args, **kwargs):
        line = " ".join(str(a) for a in args)
        _logs.append(line)
        if len(_logs) > MAX_LOG_LINES:
            _logs.pop(0)
        if not _shutting_down:
            _orig(*args, **kwargs)

    builtins.print = _print


def _run_logic(logic_fn):
    try:
        logic_fn()
    except KeyboardInterrupt:
        pass


def _handle(conn, path):
    if path == "/":
        conn.send(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n")
        conn.send(_INDEX_HTML)
    elif path == "/api/log":
        conn.send(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n")
        conn.send(json.dumps(_logs).encode())
    else:
        conn.send(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")


def main(logic_fn=testLogic, port=8080):
    global _shutting_down
    _shutting_down = False
    install_print()
    logic_thread = threading.Thread(target=_run_logic, args=(logic_fn,), daemon=False)
    logic_thread.start()

    addr = socket.getaddrinfo("0.0.0.0", port)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5)
    s.setblocking(False)

    print("Log API: http://localhost:%d/api/log" % port)
    print("Nhan Ctrl+C de dung.")

    try:
        while True:
            try:
                conn, _ = s.accept()
                conn.setblocking(True)
                req = conn.recv(1024).decode("utf-8", "ignore")
                if not req:
                    conn.close()
                    continue
                path = req.split("\r\n")[0].split(" ")[1]
                _handle(conn, path)
                conn.close()
            except OSError:
                time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        _shutting_down = True
        print("Dung server (Ctrl+C).")
        logic_thread.join(timeout=1.0)
        s.close()
        os._exit(0)


if __name__ == "__main__":
    try:
        main(testLogic)
    except KeyboardInterrupt:
        pass
