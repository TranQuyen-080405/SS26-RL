"""Tab Robot Monitor — BLE (robot → PC)."""

import asyncio
import json
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from bootstrap import robot_embbed_dir

try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakError, BleakCharacteristicNotFoundError
except ImportError:
    BleakClient = None
    BleakScanner = None
    BleakError = Exception
    BleakCharacteristicNotFoundError = Exception

SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
_STD_SVC = ("00001800", "00001801", "0000180a")

_DEPLOY_DIR = robot_embbed_dir()


def _load_robot_deploy_map():
    """Đọc deploy_map.py — khớp makeRobot / BLE trên ESP32."""
    if _DEPLOY_DIR not in sys.path:
        sys.path.insert(0, _DEPLOY_DIR)
    try:
        import deploy_map as dm
    except ImportError:
        return {
            "width": 10,
            "height": 10,
            "start": (0, 0),
            "goal": (9, 9),
            "checkpoints": [],
            "walls": [],
        }

    def _norm_wall(w):
        if isinstance(w, dict):
            return (int(w["x"]), int(w["y"]), str(w["dir"]))
        return (int(w[0]), int(w[1]), str(w[2]))

    return {
        "width": int(dm.MAP_W),
        "height": int(dm.MAP_H),
        "start": tuple(dm.START),
        "goal": tuple(dm.GOAL),
        "checkpoints": [tuple(cp) for cp in (dm.CHECKPOINTS or [])],
        "walls": [_norm_wall(w) for w in (getattr(dm, "WALLS", None) or [])],
    }


_ROBOT_MAP_SPEC = _load_robot_deploy_map()

CELL = 44
MARGIN = 24
_DIR_ARROW = {"N": (0, -10), "E": (10, 0), "S": (0, 10), "W": (-10, 0)}

_PHASE_LABEL = {
    "i": "Idle (chờ Start)",
    "r": "Đang infer",
    "g": "Goal",
    "c": "Collision",
}


class MonitorMapModel:
    def __init__(self, spec=None):
        spec = spec or _ROBOT_MAP_SPEC
        self.w = int(spec["width"])
        self.h = int(spec["height"])
        self.start = tuple(spec["start"])
        self.goal = tuple(spec["goal"])
        self.checkpoints = [tuple(cp) for cp in (spec.get("checkpoints") or [])]
        self.x = self.start[0]
        self.y = self.start[1]
        self.d = "N"
        self.phase = "i"
        self.step = 0
        self.last_action = ""
        self.walls = set()
        self._init_boundary_walls()
        for w in spec.get("walls") or []:
            if w and len(w) >= 3:
                self.walls.add((int(w[0]), int(w[1]), str(w[2])))

    def apply_map_spec(self, spec):
        if not spec:
            return
        if "w" in spec:
            self.w = int(spec["w"])
        elif "width" in spec:
            self.w = int(spec["width"])
        if "h" in spec:
            self.h = int(spec["h"])
        elif "height" in spec:
            self.h = int(spec["height"])
        if "s" in spec:
            self.start = tuple(spec["s"])
        elif "start" in spec:
            self.start = tuple(spec["start"])
        if "g" in spec:
            self.goal = tuple(spec["g"])
        elif "goal" in spec:
            self.goal = tuple(spec["goal"])
        cps = spec.get("c")
        if cps is None:
            cps = spec.get("checkpoints")
        if cps is not None:
            self.checkpoints = [tuple(cp) for cp in cps]
        self.reset_robot()
        self.walls.clear()
        self._init_boundary_walls()
        for w in _ROBOT_MAP_SPEC.get("walls") or []:
            if w and len(w) >= 3:
                self.walls.add((int(w[0]), int(w[1]), str(w[2])))

    def _init_boundary_walls(self):
        self.walls.clear()
        for y in range(self.h):
            self.walls.add((0, y, "W"))
            self.walls.add((self.w - 1, y, "E"))
        for x in range(self.w):
            self.walls.add((x, 0, "S"))
            self.walls.add((x, self.h - 1, "N"))

    def reset_robot(self):
        self.x, self.y = self.start
        self.d = "N"
        self.phase = "i"
        self.step = 0
        self.last_action = ""

    def apply_ble(self, msg):
        if not msg:
            return
        prev_phase = self.phase
        if "x" in msg:
            self.x = int(msg["x"])
        if "y" in msg:
            self.y = int(msg["y"])
        if "d" in msg:
            self.d = str(msg["d"])
        if "p" in msg:
            self.phase = str(msg["p"])
        if "n" in msg:
            self.step = int(msg["n"])
        if "a" in msg:
            self.last_action = str(msg["a"])
        if "walls" in msg:
            self.walls.clear()
            self._init_boundary_walls()
            for item in msg["walls"]:
                if not item or len(item) < 3:
                    continue
                self.walls.add((int(item[0]), int(item[1]), str(item[2])))
        return prev_phase

    def phase_label(self):
        return _PHASE_LABEL.get(self.phase, self.phase)

    def robot_pos(self):
        return (self.x, self.y)


def _ble_display_name(device, adv=None):
    name = ""
    if adv is not None:
        name = (getattr(adv, "local_name", None) or "").strip()
    if not name:
        name = (device.name or "").strip()
    return name or "(khong ten)"


def _gatt_summary(client):
    lines = []
    for svc in client.services:
        lines.append("svc %s" % svc.uuid)
        for ch in svc.characteristics:
            lines.append("  ch %s props=%s" % (ch.uuid, ",".join(ch.properties)))
    return "\n".join(lines) if lines else "(khong co service)"


def _is_std_service(uuid_str):
    u = uuid_str.lower().replace("-", "")
    return any(u.startswith(s) for s in _STD_SVC)


def _find_io_chars(client):
    nus_tx = client.services.get_characteristic(TX_CHAR_UUID)
    nus_rx = client.services.get_characteristic(RX_CHAR_UUID)
    if nus_tx and nus_rx:
        return nus_tx, nus_rx

    tx_char = None
    rx_char = None
    for svc in client.services:
        if _is_std_service(svc.uuid):
            continue
        for ch in svc.characteristics:
            props = set(ch.properties)
            if tx_char is None and ("notify" in props or "indicate" in props):
                tx_char = ch
            if rx_char is None and ("write" in props or "write-without-response" in props):
                rx_char = ch
    if tx_char and rx_char:
        return tx_char, rx_char

    for ch in client.services.characteristics.values():
        props = set(ch.properties)
        if tx_char is None and ("notify" in props or "indicate" in props):
            tx_char = ch
        if rx_char is None and ("write" in props or "write-without-response" in props):
            rx_char = ch
    return tx_char, rx_char


def _has_io_chars(client):
    tx, rx = _find_io_chars(client)
    return tx is not None and rx is not None


async def _force_rescan_gatt(client):
    backend = getattr(client, "_backend", None)
    if backend is None or not hasattr(backend, "_get_services"):
        return False
    try:
        from winsdk.windows.devices.bluetooth import BluetoothCacheMode

        backend.services = None
        client.services = await backend._get_services(
            service_cache_mode=BluetoothCacheMode.UNCACHED,
            cache_mode=BluetoothCacheMode.UNCACHED,
        )
        return _has_io_chars(client)
    except Exception:
        return False


class RobotMapCanvas:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.canvas = tk.Canvas(self.frame, bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.model = MonitorMapModel()
        self.path = []
        w, h = self.model.w, self.model.h
        self.info_var = tk.StringVar(
            value="Map %dx%d — start %s goal %s — chờ dữ liệu từ robot."
            % (w, h, self.model.start, self.model.goal)
        )
        ttk.Label(self.frame, textvariable=self.info_var, anchor=tk.W).pack(fill=tk.X, pady=(4, 0))
        
        self._cell = 44
        self._offset_x = 24
        self._offset_y = 24
        
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.redraw()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _update_layout(self):
        c = self.canvas
        w, h = self.model.w, self.model.h
        cw = max(c.winfo_width(), 320)
        ch = max(c.winfo_height(), 280)
        if cw <= 1 or ch <= 1:
            c.update_idletasks()
            cw = max(c.winfo_width(), 320)
            ch = max(c.winfo_height(), 280)

        canvas_pad = 28
        cell_min = 36
        cell_max = 80

        avail_w = max(cw - 2 * canvas_pad, w * cell_min)
        avail_h = max(ch - 2 * canvas_pad, h * cell_min)
        cell = int(min(avail_w / w, avail_h / h, cell_max))
        self._cell = max(cell, cell_min)
        map_w = w * self._cell
        map_h = h * self._cell
        self._offset_x = max(canvas_pad, (cw - map_w) // 2)
        self._offset_y = max(canvas_pad, (ch - map_h) // 2)
        c.config(scrollregion=(0, 0, cw, ch))

    def cell_px(self, x, y, h):
        px = self._offset_x + x * self._cell
        py = self._offset_y + (h - 1 - y) * self._cell
        return px, py

    def cell_center(self, x, y, h):
        px, py = self.cell_px(x, y, h)
        return px + self._cell // 2, py + self._cell // 2

    def apply_map_spec(self, spec):
        self.model.apply_map_spec(spec)
        self.path = [self.model.robot_pos()]
        self._update_info()
        self.redraw()

    def _update_info(self):
        gx, gy = self.model.goal
        cp_txt = (" | CP %s" % (self.model.checkpoints,)) if self.model.checkpoints else ""
        extra = ""
        if self.model.step:
            extra += " | bước %d" % self.model.step
        if self.model.last_action:
            extra += " | " + self.model.last_action
        self.info_var.set(
            "[%s] Robot (%d,%d) %s | goal (%d,%d)%s%s"
            % (
                self.model.phase_label(),
                self.model.x,
                self.model.y,
                self.model.d,
                gx,
                gy,
                cp_txt,
                extra,
            )
        )

    def apply_ble(self, msg):
        prev_phase = self.model.apply_ble(msg)
        pos = self.model.robot_pos()
        if self.model.phase == "r" and self.model.step == 1 and prev_phase != "r":
            self.path = [pos]
        elif not self.path or self.path[-1] != pos:
            self.path.append(pos)
        self._update_info()
        self.redraw()

    def reset_to_start(self):
        self.model.reset_robot()
        self.path = [self.model.robot_pos()]
        self.model.phase = "i"
        self.model.step = 0
        self.model.last_action = ""
        self._update_info()
        self.info_var.set(
            "[Idle] Robot (%d,%d) %s | goal (%d,%d) — bấm Start infer"
            % (self.model.x, self.model.y, self.model.d, self.model.goal[0], self.model.goal[1])
        )
        self.redraw()

    def reset_path(self):
        self.path = [self.model.robot_pos()]
        self.redraw()

    def redraw(self):
        c = self.canvas
        c.delete("all")
        self._update_layout()
        m = self.model
        w, h = m.w, m.h
        start, goal = m.start, m.goal
        cps = {tuple(cp) for cp in m.checkpoints}

        # Draw grid cells
        for y in range(h):
            for x in range(w):
                px, py = self.cell_px(x, y, h)
                fill = "#ffffff"
                if (x, y) == start:
                    fill = "#a6e3a1"
                elif (x, y) == goal:
                    fill = "#f38ba8"
                elif (x, y) in cps:
                    fill = "#f9e2af"
                c.create_rectangle(px, py, px + self._cell, py + self._cell, fill=fill, outline="#45475a")
                
                # Draw black plus sign touching the square edges
                mx = px + self._cell // 2
                my = py + self._cell // 2
                c.create_line(px, my, px + self._cell, my, fill="#000000", width=3)
                c.create_line(mx, py, mx, py + self._cell, fill="#000000", width=3)

        # Draw coordinate labels on the outer axes
        for x in range(w):
            cx = self._offset_x + x * self._cell + self._cell // 2
            # Bottom label
            cy_bot = self._offset_y + h * self._cell + 12
            c.create_text(cx, cy_bot, text=str(x), fill="#cdd6f4", font=("Segoe UI", 8, "bold"))
            # Top label
            cy_top = self._offset_y - 12
            c.create_text(cx, cy_top, text=str(x), fill="#cdd6f4", font=("Segoe UI", 8, "bold"))

        for y in range(h):
            cy = self._offset_y + (h - 1 - y) * self._cell + self._cell // 2
            # Left label
            cx_left = self._offset_x - 12
            c.create_text(cx_left, cy, text=str(y), fill="#cdd6f4", font=("Segoe UI", 8, "bold"))
            # Right label
            cx_right = self._offset_x + w * self._cell + 12
            c.create_text(cx_right, cy, text=str(y), fill="#cdd6f4", font=("Segoe UI", 8, "bold"))

        # Draw walls
        for y in range(h):
            for x in range(w):
                px, py = self.cell_px(x, y, h)
                for d, x1, y1, x2, y2 in [
                    ("N", px, py, px + self._cell, py),
                    ("E", px + self._cell, py, px + self._cell, py + self._cell),
                    ("S", px, py + self._cell, px + self._cell, py + self._cell),
                    ("W", px, py, px, py + self._cell),
                ]:
                    is_wall = (x, y, d) in m.walls
                    color = "#f38ba8" if is_wall else "#585b70"
                    width = 5 if is_wall else 2
                    c.create_line(x1, y1, x2, y2, fill=color, width=width)

        if self.path:
            pts = [self.cell_center(self.path[0][0], self.path[0][1], h)]
            for x, y in self.path[1:]:
                pts.append(self.cell_center(x, y, h))
            for i in range(len(pts) - 1):
                c.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], fill="#89b4fa", width=3)

        cx, cy = self.cell_center(m.x, m.y, h)
        r = self._cell // 4
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#cba6f7", outline="#cdd6f4", width=2)
        arrow_len = max(8, self._cell // 4)
        dir_offsets = {
            "N": (0, -arrow_len),
            "E": (arrow_len, 0),
            "S": (0, arrow_len),
            "W": (-arrow_len, 0)
        }
        dx, dy = dir_offsets.get(m.d, (0, -arrow_len))
        c.create_line(cx, cy, cx + dx, cy + dy, fill="#1e1e2e", width=3, arrow=tk.LAST, arrowshape=(8, 10, 4))


class RobotMonitorApp:
    def __init__(self, parent=None, root=None):
        if parent is None:
            self.root = tk.Tk()
            self.root.title("SS26 Robot Monitor — BLE")
            self.root.geometry("1100x640")
            self.root.minsize(800, 480)
            self.container = self.root
            self._standalone = True
        else:
            self.root = root or parent.winfo_toplevel()
            self.container = parent
            self._standalone = False

        if BleakScanner is None:
            messagebox.showerror("BLE", "Cần cài bleak: pip install bleak")
            if self._standalone:
                sys.exit(1)
            return

        self._devices = []
        self._address = None
        self._connected = False
        self._stop_ble = threading.Event()
        self._ble_thread = None
        self._client = None
        self._rx_char = None
        self._tx_buf = ""
        self._start_infer_event = threading.Event()
        self._infer_running = False
        self._build_ui()

    def _build_ui(self):
        bar = ttk.Frame(self.container, padding=8)
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="Tên BLE:").pack(side=tk.LEFT, padx=(0, 4))
        self.ble_name_var = tk.StringVar(value="Robot")
        self.entry_ble_name = ttk.Entry(bar, textvariable=self.ble_name_var, width=15)
        self.entry_ble_name.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_connect = ttk.Button(bar, text="Kết nối", command=self.toggle_connect)
        self.btn_connect.pack(side=tk.LEFT, padx=2)
        self.btn_start = ttk.Button(bar, text="Start infer", command=self.request_start_infer, state=tk.DISABLED)
        self.btn_start.pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Xóa log", command=self.clear_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Chạy lại", command=self.reset_for_rerun).pack(side=tk.LEFT, padx=2)

        self.infer_var = tk.StringVar(value="Infer: chưa chạy")
        ttk.Label(bar, textvariable=self.infer_var, width=28).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(
            value="Nhập tên BLE → Kết nối → Start infer."
        )
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

        paned = ttk.Panedwindow(self.container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        log_frame = ttk.LabelFrame(paned, text="Terminal robot (print)", padding=4)
        self.log = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#11111b",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.configure(state=tk.DISABLED)

        map_frame = ttk.LabelFrame(paned, text="Robot map (từ BLE)", padding=4)
        self.map_view = RobotMapCanvas(map_frame)
        self.map_view.pack(fill=tk.BOTH, expand=True)

        paned.add(log_frame, weight=1)
        paned.add(map_frame, weight=1)

    def append_log(self, text):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def clear_log(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def reset_for_rerun(self):
        if not self._connected:
            messagebox.showwarning("BLE", "Kết nối robot trước.")
            return
        self._start_infer_event.clear()
        self._infer_running = False
        self.map_view.reset_to_start()
        self._set_infer_status("Infer: sẵn sàng — bấm Start infer", running=False)
        self.status_var.set("Đã reset — đặt robot về ô start, bấm Start infer để chạy lại.")
        self.append_log("--- PC reset (start, path) — cho Start infer ---\n")

    def reset_path(self):
        self.map_view.reset_path()

    def toggle_connect(self):
        if self._connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        if self._ble_thread:
            return
        self._stop_ble.clear()
        self._start_infer_event.clear()
        self._ble_thread = threading.Thread(target=self._ble_loop, daemon=True)
        self._ble_thread.start()
        self.btn_connect.configure(text="Ngắt")
        self.status_var.set("Đang quét tìm và kết nối thiết bị BLE...")

    def disconnect(self):
        self._stop_ble.set()
        self._start_infer_event.set()
        self._connected = False
        self._client = None
        self._rx_char = None
        self._tx_buf = ""
        self.btn_connect.configure(text="Kết nối")
        self.btn_start.configure(state=tk.DISABLED)
        self.status_var.set("Đã ngắt kết nối.")
        self._set_infer_status("Infer: chưa kết nối", running=False)
        if self._ble_thread:
            self._ble_thread.join(timeout=3.0)
            self._ble_thread = None

    def _set_infer_status(self, text, running=None):
        self.infer_var.set(text)
        if running is not None:
            self._infer_running = running
            if running:
                self.btn_start.configure(state=tk.DISABLED)
            elif self._connected:
                self.btn_start.configure(state=tk.NORMAL)

    def _handle_ble_state(self, state):
        self.map_view.apply_ble(state)
        phase = state.get("p", "")
        if phase == "r":
            self._set_infer_status("Infer: đang chạy (bước %d)" % state.get("n", 0), running=True)
        elif phase == "g":
            self._set_infer_status("Infer: GOAL ✓ — bấm Chạy lại rồi Start infer", running=False)
        elif phase == "c":
            self._set_infer_status("Infer: dừng (collision) — bấm Chạy lại rồi Start infer", running=False)
        elif phase == "i":
            if not self._infer_running:
                self._set_infer_status("Infer: idle — bấm Start infer", running=False)

    def _handle_ble_log(self, text):
        self.append_log(text)
        line = text.strip()
        if "RX START" in line:
            self.status_var.set("Robot đã nhận lệnh Start...")
        elif "START OK" in line or "infer loop" in line:
            self._set_infer_status("Infer: đang chạy", running=True)
            self.status_var.set("Robot đã bắt đầu infer.")
        elif line.startswith("GOAL"):
            self._set_infer_status("Infer: GOAL ✓ — bấm Chạy lại rồi Start infer", running=False)
        elif "Episode ket thuc" in line or "Het episode" in line:
            self._set_infer_status("Infer: sẵn sàng — bấm Start infer", running=False)
            self.status_var.set("Robot chờ Start — bấm Chạy lại (map) rồi Start infer.")

    def request_start_infer(self):
        if not self._connected:
            messagebox.showwarning("BLE", "Kết nối robot trước.")
            return
        self._start_infer_event.set()
        self._set_infer_status("Infer: đang gửi Start...", running=False)
        self.status_var.set("Đã gửi lệnh Start infer — chờ robot phản hồi...")

    def _on_tx_notify(self, _handle, data):
        try:
            chunk = bytes(data).decode("utf-8", errors="replace")
        except Exception:
            return
        self._tx_buf += chunk
        while "\n" in self._tx_buf:
            line, self._tx_buf = self._tx_buf.split("\n", 1)
            if not line:
                continue
            if line.startswith("S:"):
                try:
                    state = json.loads(line[2:])
                except Exception as exc:
                    bad = line[:80]
                    self.root.after(
                        0,
                        lambda e=exc, b=bad: self.append_log("L:[parse err] %s | %s...\n" % (e, b)),
                    )
                    continue
                self.root.after(0, lambda s=state: self._handle_ble_state(s))
            elif line.startswith("M:"):
                try:
                    meta = json.loads(line[2:])
                except Exception as exc:
                    bad = line[:80]
                    self.root.after(
                        0,
                        lambda e=exc, b=bad: self.append_log("L:[map parse err] %s | %s...\n" % (e, b)),
                    )
                    continue
                self.root.after(0, lambda m=meta: self.map_view.apply_map_spec(m))
            elif line.startswith("L:"):
                text = line[2:] + "\n"
                self.root.after(0, lambda t=text: self._handle_ble_log(t))
            else:
                text = line + "\n"
                self.root.after(0, lambda t=text: self._handle_ble_log(t))

    async def _write_rx(self, client, payload):
        if self._rx_char is None:
            raise BleakError("Chua tim thay RX characteristic")
        await client.write_gatt_char(self._rx_char, payload, response=False)

    async def _send_start(self, client):
        await self._write_rx(client, b"S")

    async def _wait_io_gatt(self, client, timeout=12.0):
        steps = max(1, int(timeout / 0.35))
        rescanned = False
        for i in range(steps):
            if not client.is_connected:
                return False
            if _has_io_chars(client):
                return True
            if not rescanned and i >= 2:
                rescanned = await _force_rescan_gatt(client)
            await asyncio.sleep(0.35)
        if not rescanned:
            await _force_rescan_gatt(client)
        return _has_io_chars(client)

    async def _connect_with_gatt(self, device):
        last_err = None
        for attempt, use_cache in enumerate((False, True)):
            client = BleakClient(device, timeout=45.0, winrt={"use_cached_services": use_cache})
            try:
                await client.connect()
                if not client.is_connected:
                    raise BleakError("Ket noi that bai")
                if await self._wait_io_gatt(client):
                    return client
                detail = _gatt_summary(client)
                raise BleakError(
                    "Khong thay TX(notify)+RX(write). GATT:\n"
                    + detail
                    + "\n--- Xoa thiet bi cu trong Bluetooth Windows, upload ble_monitor.py len robot."
                )
            except Exception as exc:
                last_err = exc
                if client.is_connected:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                if attempt == 0:
                    await asyncio.sleep(1.5)
        raise last_err or BleakError("Khong ket noi duoc GATT")

    def _ble_loop(self):
        async def _run():
            client = None
            try:
                target_name = self.ble_name_var.get().strip()
                if not target_name:
                    raise BleakError("Nhập tên thiết bị BLE cần kết nối.")

                self.root.after(0, lambda: self.status_var.set("Đang quét tìm thiết bị '%s'..." % target_name))

                device = None
                scan_event = asyncio.Event()

                def detection_callback(d, ad):
                    nonlocal device
                    name = _ble_display_name(d, ad)
                    if target_name.lower() in name.lower():
                        device = d
                        scan_event.set()

                scanner = BleakScanner(detection_callback=detection_callback)
                await scanner.start()
                try:
                    await asyncio.wait_for(scan_event.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                finally:
                    await scanner.stop()

                if device is None:
                    raise BleakError("Không tìm thấy thiết bị BLE '%s' trong 5 giây." % target_name)

                self._address = device.address
                self._tx_buf = ""
                client = await self._connect_with_gatt(device)
                self.root.after(0, lambda a=device.address: self.append_log("Ket noi MAC: %s\n" % a))

                tx_char, rx_char = _find_io_chars(client)
                if not tx_char or not rx_char:
                    detail = _gatt_summary(client)
                    self.root.after(0, lambda d=detail: self.append_log("GATT:\n" + d + "\n"))
                    raise BleakError("Thieu TX/RX.")

                await client.start_notify(tx_char, self._on_tx_notify)

                self._client = client
                self._rx_char = rx_char
                self._connected = True
                self.root.after(0, lambda: self.map_view.reset_to_start())
                self.root.after(0, lambda: self._set_infer_status("Infer: idle — bấm Start infer", running=False))
                self.root.after(
                    0,
                    lambda: (
                        self.status_var.set("Da ket noi — bam Start infer hoac nut board."),
                        self.btn_start.configure(state=tk.NORMAL),
                    ),
                )

                while not self._stop_ble.is_set():
                    if not client.is_connected:
                        break
                    if self._start_infer_event.is_set():
                        self._start_infer_event.clear()
                        try:
                            await self._send_start(client)
                            self.root.after(
                                0,
                                lambda: self.status_var.set("Lenh Start infer da gui — cho robot phan hoi..."),
                            )
                        except Exception as exc:
                            self.root.after(0, lambda e=exc: self.status_var.set("Loi gui Start: %s" % e))
                    await asyncio.sleep(0.15)

            except BleakCharacteristicNotFoundError as exc:
                hint = "Upload lai ble_monitor.py len robot, xoa thiet bi cu trong Bluetooth Windows."
                err, h = exc, hint
                self.root.after(0, lambda e=err, t=h: self.status_var.set("BLE loi: %s. %s" % (e, t)))
            except Exception as exc:
                msg = str(exc)
                hint = ""
                if "Unreachable" in msg or "GATT services" in msg:
                    hint = " — reset robot, xoa thiet bi cu trong Bluetooth Windows."
                m, h = msg, hint
                self.root.after(0, lambda t=m, x=h: self.status_var.set("BLE loi: %s%s" % (t, x)))
            finally:
                self._connected = False
                self._client = None
                self._rx_char = None
                self._tx_buf = ""
                if client and client.is_connected:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                self.root.after(
                    0,
                    lambda: (
                        self.btn_connect.configure(text="Kết nối"),
                        self.btn_start.configure(state=tk.DISABLED),
                    ),
                )
                self._ble_thread = None

        asyncio.run(_run())

    def run(self):
        if self._standalone:
            self.root.mainloop()


if __name__ == "__main__":
    import os
    import sys

    _LIBS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _LIBS not in sys.path:
        sys.path.insert(0, _LIBS)
    from bootstrap import setup_paths

    setup_paths()
    RobotMonitorApp().run()
