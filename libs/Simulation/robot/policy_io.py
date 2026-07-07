"""Load / export policy - PC only (.bin)."""

import csv
import os
import random
import struct

from runtime_paths import app_data_path, bundled_path, is_frozen
from RL_lib.rl_core import N_ROWS, ACTIONS

CHECKPOINTS_DIR = app_data_path("checkpoints")
BUNDLED_CHECKPOINTS_DIR = bundled_path("checkpoints")
DEFAULT_POLICY_BASE = "policy"
DEFAULT_POLICY_BIN = os.path.join(CHECKPOINTS_DIR, "policy.bin")
BUNDLED_DEFAULT_POLICY_BIN = os.path.join(BUNDLED_CHECKPOINTS_DIR, "policy.bin")
POLICY_CSV_COLUMNS = ("q_forward", "q_rotate_left", "q_rotate_right")


def _abs(path):
    return os.path.abspath(path)


def _is_same_path(a, b):
    return os.path.normcase(_abs(a)) == os.path.normcase(_abs(b))


def is_bundled_policy_path(path):
    if not path or not is_frozen():
        return False
    try:
        common = os.path.commonpath([_abs(path), _abs(BUNDLED_CHECKPOINTS_DIR)])
    except ValueError:
        return False
    return _is_same_path(common, BUNDLED_CHECKPOINTS_DIR)


def normalize_policy_base_name(name):
    """Normalize a policy filename without the .bin suffix."""
    name = str(name).strip()
    if not name:
        raise ValueError("Ten policy khong duoc trong.")
    if name.lower().endswith(".bin"):
        name = os.path.splitext(name)[0]
    if not name or name in (".", ".."):
        raise ValueError("Ten policy khong hop le.")
    for ch in name:
        if not (ch.isalnum() or ch in ("_", "-")):
            raise ValueError("Ten chi dung chu, so, _ va -")
    return name


def suggest_new_policy_name(prefix="policy"):
    """Suggest a policy name that does not exist in writable checkpoints/."""
    existing = set(list_checkpoints())
    if prefix not in existing:
        return prefix
    for i in range(1, 1000):
        name = "%s_%02d" % (prefix, i)
        if name not in existing:
            return name
    return "%s_%d" % (prefix, len(existing) + 1)


def checkpoint_bin_path(base_name):
    return os.path.join(CHECKPOINTS_DIR, base_name + ".bin")


def _bundled_checkpoint_bin_path(base_name):
    return os.path.join(BUNDLED_CHECKPOINTS_DIR, base_name + ".bin")


def validate_q_table(q_table):
    if len(q_table) != N_ROWS:
        raise ValueError("Q-table co %d hang, can %d" % (len(q_table), N_ROWS))
    for i, row in enumerate(q_table):
        if len(row) != len(ACTIONS):
            raise ValueError("Hang %d co %d cot, can %d" % (i, len(row), len(ACTIONS)))


def copy_q_table(q_table):
    validate_q_table(q_table)
    return [list(row) for row in q_table]


def load_policy_bin(path):
    with open(path, "rb") as f:
        data = f.read()
    n_floats = len(data) // 4
    if n_floats != N_ROWS * len(ACTIONS):
        raise ValueError(
            "policy.bin co %d float, can %d" % (n_floats, N_ROWS * len(ACTIONS))
        )
    floats = struct.unpack("<%df" % n_floats, data)
    rows = []
    for s in range(N_ROWS):
        base = s * len(ACTIONS)
        rows.append(list(floats[base : base + len(ACTIONS)]))
    return rows


def load_q_table(bin_path=None):
    """Load Q-table from .bin. Fall back to bundled policy in frozen builds."""
    if bin_path:
        return load_policy_bin(bin_path) if os.path.isfile(bin_path) else None
    if os.path.isfile(DEFAULT_POLICY_BIN):
        return load_policy_bin(DEFAULT_POLICY_BIN)
    if os.path.isfile(BUNDLED_DEFAULT_POLICY_BIN):
        return load_policy_bin(BUNDLED_DEFAULT_POLICY_BIN)
    return None


def _bin_names_in(directory):
    if not os.path.isdir(directory):
        return []
    return sorted(
        name for name in os.listdir(directory) if name.lower().endswith(".bin")
    )


def list_checkpoints():
    """List checkpoint base names from bundled and writable checkpoints/."""
    names = set()
    for directory in (BUNDLED_CHECKPOINTS_DIR, CHECKPOINTS_DIR):
        for name in _bin_names_in(directory):
            base, ext = os.path.splitext(name)
            if ext.lower() == ".bin" and base:
                names.add(base)
    return sorted(names)


def list_policy_bin_files():
    """List .bin filenames for inference selection."""
    return sorted(set(_bin_names_in(BUNDLED_CHECKPOINTS_DIR)) | set(_bin_names_in(CHECKPOINTS_DIR)))


def policy_bin_path(filename):
    """Return a readable policy path, preferring writable checkpoints/."""
    name = os.path.basename(filename)
    if not name.lower().endswith(".bin"):
        name = name + ".bin"
    external = os.path.join(CHECKPOINTS_DIR, name)
    if os.path.isfile(external):
        return external
    bundled = os.path.join(BUNDLED_CHECKPOINTS_DIR, name)
    if os.path.isfile(bundled):
        return bundled
    return external


def resolve_checkpoint(spec):
    """
    spec: None / '' -> None (new train);
          base name ('policy') -> checkpoints/policy.bin;
          direct .bin path.
    Return (q_table, label) or (None, None) for new train.
    """
    if not spec:
        return None, None
    spec = str(spec).strip()
    if not spec:
        return None, None

    if os.path.isfile(spec):
        if not spec.lower().endswith(".bin"):
            raise ValueError("Checkpoint phai la file .bin: %s" % spec)
        return load_policy_bin(spec), spec

    base = os.path.basename(spec)
    if base.lower().endswith(".bin"):
        base = os.path.splitext(base)[0]
    for bin_path in (checkpoint_bin_path(base), _bundled_checkpoint_bin_path(base)):
        if os.path.isfile(bin_path):
            return load_policy_bin(bin_path), bin_path
    raise FileNotFoundError(
        "Khong tim thay checkpoint '%s' trong checkpoints/ (.bin)" % base
    )


def export_policy(q_table, bin_path=None):
    """Write Q-table to a writable policy.bin."""
    validate_q_table(q_table)
    bin_path = bin_path or DEFAULT_POLICY_BIN
    os.makedirs(os.path.dirname(bin_path) or ".", exist_ok=True)
    flat = []
    for row in q_table:
        flat.extend(row)
    with open(bin_path, "wb") as f:
        f.write(struct.pack("<%df" % len(flat), *flat))


def export_policy_csv(q_table, csv_path):
    """Export Q-table using the Kaggle submission schema: id + three Q-values."""
    validate_q_table(q_table)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(("id",) + POLICY_CSV_COLUMNS)
        for state_id, row in enumerate(q_table):
            writer.writerow((state_id,) + tuple(row))


def export_checkpoint(q_table, base_name):
    """Export named checkpoint into writable checkpoints/."""
    export_policy(q_table, bin_path=checkpoint_bin_path(base_name))


def empty_q_table(forward_bias=0.05):
    """forward_bias nhẹ — tránh kẹt xoay khi Q còn toàn 0."""
    return [[forward_bias, 0.0, 0.0] for _ in range(N_ROWS)]


def biased_q_table(preferred_action="forward", preferred_value=0.5, other_value=0.0):
    """Q-table ưu tiên một action cho mọi state."""
    action_to_idx = {name: i for i, name in enumerate(ACTIONS)}
    idx = action_to_idx.get(preferred_action, 0)
    row = [float(other_value)] * len(ACTIONS)
    row[idx] = float(preferred_value)
    return [list(row) for _ in range(N_ROWS)]


def random_q_table(choices=(-0.5, 0.0, 0.5)):
    """Q-table ngẫu nhiên rời rạc: mỗi ô chọn từ choices."""
    vals = [float(v) for v in choices]
    if not vals:
        vals = [-0.5, 0.0, 0.5]
    table = []
    for _ in range(N_ROWS):
        table.append([random.choice(vals) for _ in ACTIONS])
    return table
