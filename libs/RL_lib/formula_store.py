"""Lưu / nạp công thức reward học sinh (.json trong reward_formula/ cạnh main.py)."""

import json
import os
import re

from runtime_paths import app_data_path

_REPO_ROOT = app_data_path()
FORMULA_DIR = app_data_path("reward_formula")
_SCHEMA_VERSION = 1
_DEFAULT_BLOCK_WEIGHT = 1.0


def ensure_formula_dir():
    os.makedirs(FORMULA_DIR, exist_ok=True)


def normalize_formula_basename(name):
    """Tên file an toàn (không .json)."""
    raw = str(name or "").strip()
    if not raw:
        raise ValueError("Chưa đặt tên công thức")
    base = os.path.splitext(raw)[0].strip()
    base = re.sub(r'[<>:"/\\|?*]', "_", base)
    base = base.strip(" .")
    if not base:
        raise ValueError("Tên công thức không hợp lệ")
    return base


def formula_json_path(name):
    base = normalize_formula_basename(name)
    return os.path.join(FORMULA_DIR, base + ".json")


def list_saved_formulas():
    ensure_formula_dir()
    out = []
    for fname in os.listdir(FORMULA_DIR):
        if not fname.lower().endswith(".json"):
            continue
        out.append(os.path.splitext(fname)[0])
    return sorted(out, key=str.lower)


def build_snapshot(enabled_modules, total_formula, element_weights, thresholds):
    return {
        "version": _SCHEMA_VERSION,
        "enabled_modules": sorted(enabled_modules),
        "total_formula": str(total_formula or "").strip(),
        "element_weights": dict(element_weights),
        "thresholds": dict(thresholds),
    }


def save_formula_file(name, snapshot):
    ensure_formula_dir()
    path = formula_json_path(name)
    payload = dict(snapshot)
    payload["name"] = normalize_formula_basename(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def delete_formula_file(name):
    path = formula_json_path(name)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False



def load_formula_file(name):
    path = formula_json_path(name)
    if not os.path.isfile(path):
        raise FileNotFoundError("Không tìm thấy: %s" % os.path.basename(path))
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("File JSON không hợp lệ")
    return migrate_formula_snapshot(data)


_LEGACY_REWARD_LABELS = {
    "Vào lại ô cũ": "Quay lại ô",
    "Lặp ô (tổng)": "Lặp ô gần",
    "Lặp ô tổng": "Lặp ô gần",
    "Lại gần đích": "Lại gần goal",
    "Thay đổi khoảng cách tới Goal": "Lại gần goal",
    "Thay đổi khoảng cách tới Checkpoint": "Lại gần checkpoint",
    "Lại gần checkpoint 1": "Lại gần checkpoint",
    "Lại gần checkpoint 2": "Lại gần checkpoint",
    "Lại gần checkpoint 3": "Lại gần checkpoint",
    "Đi xa checkpoint 1": "Đi xa checkpoint",
    "Đi xa checkpoint 2": "Đi xa checkpoint",
    "Đi xa checkpoint 3": "Đi xa checkpoint",
    "Chạm checkpoint 1": "Chạm checkpoint",
    "Chạm checkpoint 2": "Chạm checkpoint",
    "Chạm checkpoint 3": "Chạm checkpoint",
    "Giữ nguyên hướng đi": "Giữ hướng n lần thì cộng",
}


def migrate_formula_snapshot(data):
    """Nâng cấp snapshot cũ (revisit / visit_total → visit_window / visit_repeat)."""
    from RL_lib.lab_registry import REWARD_ELEMENTS

    out = dict(data)
    weights = dict(out.get("element_weights") or {})
    if "revisit" in weights:
        weights.setdefault("visit_repeat", weights.pop("revisit"))
    if "visit_total" in weights:
        weights.setdefault("visit_window", weights.pop("visit_total"))

    # Handle goal_trend
    if "goal_trend" in weights:
        val = weights.pop("goal_trend")
        weights.setdefault("goal_closer", val)
        weights.setdefault("goal_farther", -val)

    # Handle cp_trend
    if "cp_trend" in weights:
        val = weights.pop("cp_trend")
        weights.setdefault("cp_closer", val)
        weights.setdefault("cp_farther", -val)

    # Handle split CP keys (older migration) -> shared keys
    legacy_cp_closer = weights.pop("cp1_closer", None)
    if legacy_cp_closer is None:
        legacy_cp_closer = weights.pop("cp2_closer", None)
    if legacy_cp_closer is None:
        legacy_cp_closer = weights.pop("cp3_closer", None)
    if legacy_cp_closer is not None:
        weights.setdefault("cp_closer", legacy_cp_closer)

    legacy_cp_farther = weights.pop("cp1_farther", None)
    if legacy_cp_farther is None:
        legacy_cp_farther = weights.pop("cp2_farther", None)
    if legacy_cp_farther is None:
        legacy_cp_farther = weights.pop("cp3_farther", None)
    if legacy_cp_farther is not None:
        weights.setdefault("cp_farther", legacy_cp_farther)

    legacy_checkpoint = weights.pop("checkpoint1", None)
    if legacy_checkpoint is None:
        legacy_checkpoint = weights.pop("checkpoint2", None)
    if legacy_checkpoint is None:
        legacy_checkpoint = weights.pop("checkpoint3", None)
    if legacy_checkpoint is not None:
        weights.setdefault("checkpoint", legacy_checkpoint)

    # Handle straight_streak
    if "straight_streak" in weights:
        val = weights.pop("straight_streak")
        weights.setdefault("straight_streak_reach", val)
        weights.setdefault("straight_streak_cap", val)

    for eid in REWARD_ELEMENTS:
        weights.setdefault(eid, _DEFAULT_BLOCK_WEIGHT)

    out["element_weights"] = weights

    thresholds = dict(out.get("thresholds") or {})
    if "MAX_REVISIT_STEPS" not in thresholds:
        if "MAX_NODE_VISITS" in thresholds:
            thresholds["MAX_REVISIT_STEPS"] = thresholds.pop("MAX_NODE_VISITS")
        elif "MAX_NODE_REVISITS" in thresholds:
            thresholds["MAX_REVISIT_STEPS"] = thresholds.pop("MAX_NODE_REVISITS")
    thresholds.setdefault("MAX_REVISIT_STEPS", 5)
    thresholds.setdefault("MAX_CELL_REPEAT", 3)
    thresholds.setdefault("MAX_PING_PONG_CYCLES", 1)
    thresholds.setdefault("MAX_PING_PONG_SPAN", 5)
    thresholds.setdefault("CP_TARGET_INDEX", 1)
    if "MAX_STRAIGHT_STREAK" in thresholds:
        val = thresholds.pop("MAX_STRAIGHT_STREAK")
        thresholds.setdefault("MAX_STRAIGHT_REACH", val)
        thresholds.setdefault("MAX_STRAIGHT_CAP", val)
    thresholds.setdefault("MAX_STRAIGHT_REACH", 3)
    thresholds.setdefault("MAX_STRAIGHT_CAP", 3)
    thresholds.pop("MAX_NODE_VISITS", None)
    thresholds.pop("MAX_NODE_REVISITS", None)
    out["thresholds"] = thresholds

    instance_configs = dict(out.get("instance_configs") or {})
    migrated_instances = {}
    for iid, cfg in instance_configs.items():
        if not isinstance(cfg, dict):
            continue
        eid = str(cfg.get("eid", iid.split("#", 1)[0]))
        new_eid = eid
        cp_target = None
        if eid in ("cp1_closer", "cp2_closer", "cp3_closer"):
            new_eid = "cp_closer"
            cp_target = int(eid[2])
        elif eid in ("cp1_farther", "cp2_farther", "cp3_farther"):
            new_eid = "cp_farther"
            cp_target = int(eid[2])
        elif eid in ("checkpoint1", "checkpoint2", "checkpoint3"):
            new_eid = "checkpoint"
            cp_target = int(eid[-1])
        new_iid = iid
        if new_eid != eid and "#" in iid:
            _, suffix = iid.split("#", 1)
            new_iid = "%s#%s" % (new_eid, suffix)
        if new_iid in migrated_instances and "#" in new_iid:
            base, idx_s = new_iid.split("#", 1)
            try:
                idx = int(idx_s)
            except ValueError:
                idx = 1
            while "%s#%d" % (base, idx) in migrated_instances:
                idx += 1
            new_iid = "%s#%d" % (base, idx)
        new_cfg = dict(cfg)
        new_cfg["eid"] = new_eid
        if cp_target is not None:
            t = dict(new_cfg.get("thresholds") or {})
            t.setdefault("CP_TARGET_INDEX", cp_target)
            new_cfg["thresholds"] = t
        migrated_instances[new_iid] = new_cfg
    instance_configs = migrated_instances

    # Backward compatibility: threshold_instances {eid#idx:KEY -> value}
    for key, val in (out.get("threshold_instances") or {}).items():
        if ":" not in str(key):
            continue
        iid, tk_key = str(key).split(":", 1)
        cfg = instance_configs.setdefault(
            iid, {"eid": iid.split("#", 1)[0], "weight": _DEFAULT_BLOCK_WEIGHT, "thresholds": {}}
        )
        cfg.setdefault("thresholds", {})[tk_key] = val
    out["instance_configs"] = instance_configs

    expr = str(out.get("total_formula") or "")
    for old, new in _LEGACY_REWARD_LABELS.items():
        expr = expr.replace(old, new)
    out["total_formula"] = expr
    return out
