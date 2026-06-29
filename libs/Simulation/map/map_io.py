"""
Đọc / ghi map JSON cho editor và Simulation.
Lưu tại: <repo>/map/train/map_train_*.json | <repo>/map/infer/map_infer_*.json
"""

import json
import os
import re

_SIM_MAP_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SIM_MAP_DIR, "..", ".."))
MAP_ROOT = os.path.join(_REPO_ROOT, "map")
TRAIN_MAPS_DIR = os.path.join(MAP_ROOT, "train")
INFER_MAPS_DIR = os.path.join(MAP_ROOT, "infer")
# Tương thích import cũ
MAPS_DIR = MAP_ROOT

_KIND_PREFIX = {"train": "map_train_", "infer": "map_infer_"}


def maps_dir_for_kind(kind):
    if kind == "infer":
        return INFER_MAPS_DIR
    return TRAIN_MAPS_DIR


def ensure_maps_dir(kind="train"):
    os.makedirs(maps_dir_for_kind(kind), exist_ok=True)


def default_spec(width=10, height=10, name="untitled", kind="train"):
    return {
        "name": name,
        "kind": kind,
        "width": width,
        "height": height,
        "start": [0, 0],
        "goal": [width - 1, height - 1],
        "checkpoints": [],
        "walls": [],
    }


def _normalize_spec(spec):
    out = dict(spec)
    out["start"] = list(spec["start"])
    out["goal"] = list(spec["goal"])
    out["checkpoints"] = [list(c) for c in spec.get("checkpoints") or []]
    walls = []
    for w in spec.get("walls") or []:
        if isinstance(w, dict):
            walls.append({"x": int(w["x"]), "y": int(w["y"]), "dir": w["dir"]})
        else:
            walls.append({"x": int(w[0]), "y": int(w[1]), "dir": w[2]})
    out["walls"] = walls
    return out


def walls_set_from_spec(spec):
    s = set()
    for w in spec.get("walls") or []:
        s.add((int(w["x"]), int(w["y"]), w["dir"]))
    return s


def spec_from_walls(width, height, walls_set, **kwargs):
    spec = default_spec(width, height, name=kwargs.get("name", "untitled"), kind=kwargs.get("kind", "train"))
    if "start" in kwargs:
        spec["start"] = list(kwargs["start"])
    if "goal" in kwargs:
        spec["goal"] = list(kwargs["goal"])
    if "checkpoints" in kwargs:
        spec["checkpoints"] = [list(c) for c in kwargs["checkpoints"]]
    spec["walls"] = [{"x": x, "y": y, "dir": d} for x, y, d in sorted(walls_set)]
    return spec


def save_map_json(spec, path=None, kind=None):
    """Lưu spec ra JSON trong map/train/ hoặc map/infer/."""
    spec = _normalize_spec(spec)
    if kind:
        spec["kind"] = kind
    k = spec.get("kind", "train")
    ensure_maps_dir(k)
    if path is None:
        safe = re.sub(r"[^\w\-]+", "_", spec.get("name", "map")).strip("_") or "map"
        prefix = _KIND_PREFIX.get(k, "map_train_")
        path = os.path.join(maps_dir_for_kind(k), "%s%s.json" % (prefix, safe))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    return path


def load_map_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return _normalize_spec(json.load(f))


def build_sim_map(spec):
    """Nạp spec JSON → sim_map dict (dùng cho train / infer)."""
    import sys

    _sim_root = os.path.abspath(os.path.join(_SIM_MAP_DIR, ".."))
    if _sim_root not in sys.path:
        sys.path.insert(0, _sim_root)
    from map import sim_map as sm

    spec = _normalize_spec(spec)
    sim = sm.init_sim_map(
        spec["width"],
        spec["height"],
        goal=tuple(spec["goal"]),
        checkpoints=[tuple(c) for c in spec["checkpoints"]],
        start=tuple(spec["start"]),
    )
    for w in spec["walls"]:
        sm.set_wall(sim, w["x"], w["y"], w["dir"], True)
    sim["name"] = spec.get("name", "unnamed")
    sim["kind"] = spec.get("kind", "train")
    sim["source"] = spec
    return sim


def build_sim_map_from_file(path):
    return build_sim_map(load_map_json(path))


def list_map_files(kind=None):
    """Liệt kê mọi file .json trong map/train/ hoặc map/infer/."""
    ensure_maps_dir("train")
    ensure_maps_dir("infer")

    def _json_in_dir(directory):
        if not os.path.isdir(directory):
            return []
        return sorted(
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.lower().endswith(".json")
        )

    if kind == "train":
        return _json_in_dir(TRAIN_MAPS_DIR)
    if kind == "infer":
        return _json_in_dir(INFER_MAPS_DIR)
    return _json_in_dir(TRAIN_MAPS_DIR) + _json_in_dir(INFER_MAPS_DIR)
