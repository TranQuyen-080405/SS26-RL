"""Load policy — MicroPython (.bin only, memoryview — tiết kiệm RAM)."""

import os
import struct

from modules.logics.rl_core import N_ROWS, ACTIONS

_Q_TABLE_DIR = "modules/logics/Q_table"
_POLICY_MV = None
_LOADED_NAME = None


def _find_bin(folder=_Q_TABLE_DIR):
    """Tìm file .bin đầu tiên trong folder Q_table."""
    try:
        for name in os.listdir(folder):
            if name.endswith(".bin"):
                return folder + "/" + name
    except OSError:
        pass
    return None


def load_policy_bin(path=None):
    """Nạp file .bin vào memoryview. Nếu path=None, tự tìm trong Q_table."""
    global _POLICY_MV, _LOADED_NAME
    if path is None:
        path = _find_bin()
    if path is None:
        _POLICY_MV = None
        _LOADED_NAME = None
        return False
    try:
        with open(path, "rb") as f:
            data = f.read()
        need = N_ROWS * len(ACTIONS) * 4
        if len(data) != need:
            return False
        _POLICY_MV = memoryview(data)
        _LOADED_NAME = path
        return True
    except Exception:
        _POLICY_MV = None
        _LOADED_NAME = None
        return False


def loaded_name():
    """Trả về tên file .bin đã load (hoặc None)."""
    return _LOADED_NAME


def policy_loaded():
    return _POLICY_MV is not None


def get_policy_for_state(encoded_state):
    if _POLICY_MV is None or encoded_state < 0 or encoded_state >= N_ROWS:
        return ACTIONS[0]
    base = encoded_state * len(ACTIONS) * 4
    try:
        q0, q1, q2 = struct.unpack_from("<3f", _POLICY_MV, base)
    except Exception:
        return ACTIONS[0]
    row = (q0, q1, q2)
    best = 0
    for i in range(1, len(row)):
        if row[i] > row[best]:
            best = i
    return ACTIONS[best]
