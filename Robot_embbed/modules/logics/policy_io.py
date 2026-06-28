"""Load policy — MicroPython (.bin only, memoryview — tiết kiệm RAM)."""

import struct

from modules.logics.rl_core import N_ROWS, ACTIONS

_DEFAULT_POLICY_BIN = "modules/logics/Q_table/policy.bin"
_POLICY_MV = None


def load_policy_bin(path=_DEFAULT_POLICY_BIN):
    """Nạp policy.bin vào memoryview. Trả True nếu OK."""
    global _POLICY_MV
    try:
        with open(path, "rb") as f:
            data = f.read()
        need = N_ROWS * len(ACTIONS) * 4
        if len(data) != need:
            return False
        _POLICY_MV = memoryview(data)
        return True
    except Exception:
        _POLICY_MV = None
        return False


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
