import socket
import json
import time
import _thread
try:
    from public_wifi import setup_wifi
except ImportError:
    from modules.server.public_wifi import setup_wifi

MAX_LOG_LINES = 1000
_logs = []
_html = 'modules/UI/terminal.html'
_css = 'modules/UI/terminal.css'


def install_print():
    import builtins
    _orig = builtins.print

    def _print(*args, **kwargs):
        line = ' '.join(str(a) for a in args)
        _logs.append(line)
        if len(_logs) > MAX_LOG_LINES:
            _logs.pop(0)
        try:
            _orig(*args, **kwargs)
        except Exception:
            pass

    builtins.print = _print


def _send_file(conn, path, content_type):
    conn.send(('HTTP/1.1 200 OK\r\nContent-Type: %s\r\nConnection: close\r\n\r\n' % content_type).encode())
    with open(path, 'r') as f:
        conn.send(f.read().encode())


def start(logic_run, port=80):
    install_print()
    ip = setup_wifi()
    _thread.start_new_thread(logic_run, ())

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', port))
    s.listen(2)
    s.setblocking(False)
    print('Terminal: http://%s' % ip)

    while True:
        try:
            conn, _ = s.accept()
            conn.setblocking(True)
            req = conn.recv(1024).decode('utf-8', 'ignore')
            if not req:
                conn.close()
                continue
            path = req.split('\r\n')[0].split(' ')[1]

            if path == '/':
                _send_file(conn, _html, 'text/html; charset=utf-8')
            elif path == '/terminal.css':
                _send_file(conn, _css, 'text/css; charset=utf-8')
            elif path == '/api/log':
                conn.send(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n')
                conn.send(json.dumps(_logs).encode())
            else:
                conn.send(b'HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n')
            conn.close()
        except OSError:
            time.sleep_ms(20)
