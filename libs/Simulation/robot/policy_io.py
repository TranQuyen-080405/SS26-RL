"""Load / export policy — PC only (.bin)."""

import os
import struct

from RL_lib.rl_core import N_ROWS, ACTIONS

_LIBS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_LIBS, ".."))
CHECKPOINTS_DIR = os.path.join(_REPO_ROOT, "checkpoints")
DEFAULT_POLICY_BASE = "policy"
DEFAULT_POLICY_BIN = os.path.join(CHECKPOINTS_DIR, "policy.bin")


def normalize_policy_base_name(name):
    """Chuẩn hóa tên file policy (không đuôi .bin)."""
    name = str(name).strip()
    if not name:
        raise ValueError("Tên policy không được trống.")
    if name.lower().endswith(".bin"):
        name = os.path.splitext(name)[0]
    if not name or name in (".", ".."):
        raise ValueError("Tên policy không hợp lệ.")
    for ch in name:
        if not (ch.isalnum() or ch in ("_", "-")):
            raise ValueError("Tên chỉ dùng chữ, số, _ và -")
    return name


def suggest_new_policy_name(prefix="policy"):
    """Gợi ý tên policy chưa tồn tại trong checkpoints/."""
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


def validate_q_table(q_table):
    if len(q_table) != N_ROWS:
        raise ValueError("Q-table có %d hàng, cần %d" % (len(q_table), N_ROWS))
    for i, row in enumerate(q_table):
        if len(row) != len(ACTIONS):
            raise ValueError("Hàng %d có %d cột, cần %d" % (i, len(row), len(ACTIONS)))


def copy_q_table(q_table):
    validate_q_table(q_table)
    return [list(row) for row in q_table]


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


def load_q_table(bin_path=None):
    """Đọc Q-table từ .bin. Trả None nếu không có file."""
    bin_path = bin_path or DEFAULT_POLICY_BIN
    if os.path.isfile(bin_path):
        return load_policy_bin(bin_path)
    return None


def list_checkpoints():
    """Tên checkpoint (không đuôi) trong checkpoints/ có file .bin."""
    if not os.path.isdir(CHECKPOINTS_DIR):
        return []
    names = set()
    for name in os.listdir(CHECKPOINTS_DIR):
        base, ext = os.path.splitext(name)
        if ext.lower() == ".bin" and base:
            names.add(base)
    return sorted(names)


def list_policy_bin_files():
    """Tên file .bin trong checkpoints/ (để chọn infer)."""
    if not os.path.isdir(CHECKPOINTS_DIR):
        return []
    return sorted(
        name for name in os.listdir(CHECKPOINTS_DIR) if name.lower().endswith(".bin")
    )


def policy_bin_path(filename):
    """Đường dẫn đầy đủ tới file .bin trong checkpoints/."""
    name = os.path.basename(filename)
    if not name.lower().endswith(".bin"):
        name = name + ".bin"
    return os.path.join(CHECKPOINTS_DIR, name)


def resolve_checkpoint(spec):
    """
    spec: None / '' → None (train mới);
          tên base ('policy') → checkpoints/policy.bin;
          đường dẫn file .bin.
    Trả (q_table, label) hoặc (None, None) nếu train mới.
    """
    if not spec:
        return None, None
    spec = str(spec).strip()
    if not spec:
        return None, None

    if os.path.isfile(spec):
        if not spec.lower().endswith(".bin"):
            raise ValueError("Checkpoint phải là file .bin: %s" % spec)
        return load_policy_bin(spec), spec

    base = os.path.basename(spec)
    if base.lower().endswith(".bin"):
        base = os.path.splitext(base)[0]
    bin_path = checkpoint_bin_path(base)
    if not os.path.isfile(bin_path):
        raise FileNotFoundError(
            "Không tìm thấy checkpoint '%s' trong checkpoints/ (.bin)" % base
        )
    return load_policy_bin(bin_path), bin_path


def export_policy(q_table, bin_path=None):
    """Ghi Q-table ra policy.bin."""
    validate_q_table(q_table)
    bin_path = bin_path or DEFAULT_POLICY_BIN
    os.makedirs(os.path.dirname(bin_path) or ".", exist_ok=True)
    flat = []
    for row in q_table:
        flat.extend(row)
    with open(bin_path, "wb") as f:
        f.write(struct.pack("<%df" % len(flat), *flat))


def export_checkpoint(q_table, base_name):
    """Export checkpoint đặt tên — ghi .bin trong checkpoints/."""
    export_policy(q_table, bin_path=checkpoint_bin_path(base_name))


def empty_q_table(forward_bias=0.05):
    """forward_bias nhẹ — tránh kẹt xoay khi Q còn toàn 0."""
    return [[forward_bias, 0.0, 0.0] for _ in range(N_ROWS)]
