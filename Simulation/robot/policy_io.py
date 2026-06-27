"""Load / export policy — PC only."""

import json
import os
import struct

from RL_lib.rl_core import N_ROWS, ACTIONS

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
Q_TABLE_DIR = os.path.join(_ROOT, "Q_table")
DEFAULT_POLICY_BASE = "policy"
DEFAULT_POLICY_JSON = os.path.join(Q_TABLE_DIR, "policy.json")
DEFAULT_POLICY_BIN = os.path.join(Q_TABLE_DIR, "policy.bin")


def checkpoint_json_path(base_name):
    return os.path.join(Q_TABLE_DIR, base_name + ".json")


def checkpoint_bin_path(base_name):
    return os.path.join(Q_TABLE_DIR, base_name + ".bin")


def validate_q_table(q_table):
    if len(q_table) != N_ROWS:
        raise ValueError("Q-table có %d hàng, cần %d" % (len(q_table), N_ROWS))
    for i, row in enumerate(q_table):
        if len(row) != len(ACTIONS):
            raise ValueError("Hàng %d có %d cột, cần %d" % (i, len(row), len(ACTIONS)))


def copy_q_table(q_table):
    validate_q_table(q_table)
    return [list(row) for row in q_table]


def load_policy_json(path):
    with open(path, "r", encoding="utf-8") as f:
        q = json.load(f)
    validate_q_table(q)
    return q


def load_policy_bin(path):
    with open(path, "rb") as f:
        data = f.read()
    n_floats = len(data) // 4
    if n_floats != N_ROWS * len(ACTIONS):
        raise ValueError(
            "policy.bin có %d float, cần %d" % (n_floats, N_ROWS * len(ACTIONS))
        )
    floats = struct.unpack("<%df" % n_floats, data)
    rows = []
    for s in range(N_ROWS):
        base = s * len(ACTIONS)
        rows.append(list(floats[base : base + len(ACTIONS)]))
    return rows


def load_q_table(json_path=None, bin_path=None):
    """Đọc Q-table; ưu tiên .bin nếu có, không thì .json. Trả None nếu không có file."""
    json_path = json_path or DEFAULT_POLICY_JSON
    bin_path = bin_path or DEFAULT_POLICY_BIN
    if os.path.isfile(bin_path):
        return load_policy_bin(bin_path)
    if os.path.isfile(json_path):
        return load_policy_json(json_path)
    return None


def list_checkpoints():
    """Tên checkpoint (không đuôi) trong Q_table/ có .json và/hoặc .bin."""
    if not os.path.isdir(Q_TABLE_DIR):
        return []
    names = set()
    for name in os.listdir(Q_TABLE_DIR):
        base, ext = os.path.splitext(name)
        if ext.lower() in (".json", ".bin") and base:
            names.add(base)
    return sorted(names)


def list_policy_json_files():
    """Tên file .json trong Q_table/ (để chọn infer)."""
    if not os.path.isdir(Q_TABLE_DIR):
        return []
    return sorted(
        name for name in os.listdir(Q_TABLE_DIR) if name.lower().endswith(".json")
    )


def policy_json_path(filename):
    """Đường dẫn đầy đủ tới file .json trong Q_table/."""
    return os.path.join(Q_TABLE_DIR, os.path.basename(filename))


def resolve_checkpoint(spec):
    """
    spec: None / '' → None (train mới);
          tên base ('policy') → Q_table/policy.{json,bin};
          đường dẫn file .json hoặc .bin.
  Trả (q_table, label) hoặc (None, None) nếu train mới.
    """
    if not spec:
        return None, None
    spec = str(spec).strip()
    if not spec:
        return None, None

    if os.path.isfile(spec):
        base, ext = os.path.splitext(spec)
        if ext.lower() == ".bin":
            q = load_policy_bin(spec)
            return q, spec
        if ext.lower() == ".json":
            q = load_policy_json(spec)
            return q, spec
        raise ValueError("Checkpoint phải là file .json hoặc .bin: %s" % spec)

    base = os.path.basename(spec)
    if base.endswith(".json") or base.endswith(".bin"):
        base = os.path.splitext(base)[0]
    json_path = checkpoint_json_path(base)
    bin_path = checkpoint_bin_path(base)
    q = load_q_table(json_path=json_path, bin_path=bin_path)
    if q is None:
        raise FileNotFoundError(
            "Không tìm thấy checkpoint '%s' trong Q_table/ (.json hoặc .bin)" % base
        )
    label = bin_path if os.path.isfile(bin_path) else json_path
    return q, label


def export_policy(q_table, json_path=None, bin_path=None):
    """Ghi đồng thời .json và .bin — cùng nội dung Q-table."""
    validate_q_table(q_table)
    json_path = json_path or DEFAULT_POLICY_JSON
    bin_path = bin_path or DEFAULT_POLICY_BIN
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(bin_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(q_table, f)
    flat = []
    for row in q_table:
        flat.extend(row)
    with open(bin_path, "wb") as f:
        f.write(struct.pack("<%df" % len(flat), *flat))


def export_checkpoint(q_table, base_name):
    """Export checkpoint đặt tên — đồng bộ .json + .bin trong Q_table/."""
    export_policy(
        q_table,
        json_path=checkpoint_json_path(base_name),
        bin_path=checkpoint_bin_path(base_name),
    )


def empty_q_table(forward_bias=0.05):
    """forward_bias nhẹ — tránh kẹt xoay khi Q còn toàn 0."""
    return [[forward_bias, 0.0, 0.0] for _ in range(N_ROWS)]
