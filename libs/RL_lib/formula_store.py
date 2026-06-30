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
    return data
