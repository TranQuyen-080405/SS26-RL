"""Load policy — MicroPython."""

import json

from rl_core import N_ROWS, ACTIONS


def load_policy_json(path="Q_table/policy.json"):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


def load_policy_bin(path="Q_table/policy.bin"):
    try:
        import struct

        with open(path, "rb") as f:
            data = f.read()
        n = len(data) // 4
        floats = struct.unpack("<%df" % n, data)
        rows = []
        for s in range(N_ROWS):
            base = s * len(ACTIONS)
            rows.append(list(floats[base : base + len(ACTIONS)]))
        return rows
    except Exception:
        return []
