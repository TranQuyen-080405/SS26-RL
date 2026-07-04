"""Lưu / nạp công thức reward học sinh (.json trong libs/reward_formula/)."""

import json
import os
import re

_LIBS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FORMULA_DIR = os.path.join(_LIBS_ROOT, "reward_formula")
_SCHEMA_VERSION = 1


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
    "Giữ nguyên hướng đi": "Giữ hướng n lần thì cộng",
}


def migrate_formula_snapshot(data):
    """Nâng cấp snapshot cũ (revisit / visit_total → visit_window / visit_repeat)."""
    out = dict(data)
    weights = dict(out.get("element_weights") or {})
    if "revisit" in weights:
        weights.setdefault("visit_repeat", weights.pop("revisit"))
    if "visit_total" in weights:
        weights.setdefault("visit_window", weights.pop("visit_total"))
    weights.setdefault("visit_window", 0.0)
    weights.setdefault("visit_repeat", 0.0)

    # Handle goal_trend
    if "goal_trend" in weights:
        val = weights.pop("goal_trend")
        weights.setdefault("goal_closer", val)
        weights.setdefault("goal_farther", -val)
    weights.setdefault("goal_closer", 0.0)
    weights.setdefault("goal_farther", 0.0)

    # Handle cp_trend
    if "cp_trend" in weights:
        val = weights.pop("cp_trend")
        weights.setdefault("cp_closer", val)
        weights.setdefault("cp_farther", -val)
    weights.setdefault("cp_closer", 0.0)
    weights.setdefault("cp_farther", 0.0)

    # Handle straight_streak
    if "straight_streak" in weights:
        val = weights.pop("straight_streak")
        weights.setdefault("straight_streak_reach", val)
        weights.setdefault("straight_streak_cap", val)
    weights.setdefault("straight_streak_reach", 0.0)
    weights.setdefault("straight_streak_cap", 0.0)

    # Handle wall_detected and wall_visible
    weights.setdefault("wall_detected", 0.0)
    weights.setdefault("wall_visible", 0.0)

    # Handle rotate split
    weights.setdefault("wasted_rotate", 0.0)
    weights.setdefault("blocked_rotate", 0.0)

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
    if "MAX_STRAIGHT_STREAK" in thresholds:
        val = thresholds.pop("MAX_STRAIGHT_STREAK")
        thresholds.setdefault("MAX_STRAIGHT_REACH", val)
        thresholds.setdefault("MAX_STRAIGHT_CAP", val)
    thresholds.setdefault("MAX_STRAIGHT_REACH", 3)
    thresholds.setdefault("MAX_STRAIGHT_CAP", 3)
    thresholds.pop("MAX_NODE_VISITS", None)
    thresholds.pop("MAX_NODE_REVISITS", None)
    out["thresholds"] = thresholds

    expr = str(out.get("total_formula") or "")
    for old, new in _LEGACY_REWARD_LABELS.items():
        expr = expr.replace(old, new)
    out["total_formula"] = expr
    return out
