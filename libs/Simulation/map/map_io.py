"""
Read/write map JSON for editor and Simulation.

Writable maps live under <app_root>/map/train and <app_root>/map/infer.
When packaged with PyInstaller, default infer maps can also be bundled inside
<bundle>/map/infer; those bundled maps are read-only and are merged into the
infer list without exposing files next to the exe.
"""

import json
import os
import re

from runtime_paths import app_data_path, bundled_path, is_frozen

_SIM_MAP_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = app_data_path()
MAP_ROOT = app_data_path("map")
TRAIN_MAPS_DIR = os.path.join(MAP_ROOT, "train")
INFER_MAPS_DIR = os.path.join(MAP_ROOT, "infer")
MAX_TRAIN_MAP_DIM = 5
BUNDLED_MAP_ROOT = bundled_path("map")
BUNDLED_INFER_MAPS_DIR = os.path.join(BUNDLED_MAP_ROOT, "infer")
# Backward-compatible import name.
MAPS_DIR = MAP_ROOT

_KIND_PREFIX = {"train": "map_train_", "infer": "map_infer_"}


def _abs(path):
    return os.path.abspath(path)


def _is_same_path(a, b):
    return os.path.normcase(_abs(a)) == os.path.normcase(_abs(b))


def is_bundled_map_path(path):
    """Return True for read-only maps that came from the packaged exe."""
    if not path or not is_frozen():
        return False
    try:
        common = os.path.commonpath([_abs(path), _abs(BUNDLED_MAP_ROOT)])
    except ValueError:
        return False
    return _is_same_path(common, BUNDLED_MAP_ROOT)


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
    """Save a map JSON to writable map/train or map/infer."""
    spec = _normalize_spec(spec)
    if kind:
        spec["kind"] = kind
    k = spec.get("kind", "train")
    ensure_maps_dir(k)

    orig_name = spec.get("name", "map")
    safe = re.sub(r"[^\w\-]+", "_", orig_name).strip("_") or "map"
    for pref in ["map_train_", "map_infer_"]:
        if safe.startswith(pref):
            safe = safe[len(pref):]

    prefix = _KIND_PREFIX.get(k, "map_train_")
    new_name = f"{prefix}{safe}"
    spec["name"] = new_name

    if path is None:
        path = os.path.join(maps_dir_for_kind(k), f"{new_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    return path


def load_map_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return _normalize_spec(json.load(f))


def find_oversized_train_maps(max_dim=MAX_TRAIN_MAP_DIM, paths=None):
    """Return [(basename, width, height), ...] for train maps larger than max_dim."""
    paths = paths if paths is not None else list_map_files("train")
    oversize = []
    for path in paths:
        name = os.path.basename(path)
        try:
            spec = load_map_json(path)
            w, h = int(spec["width"]), int(spec["height"])
            if w > max_dim or h > max_dim:
                oversize.append((name, w, h))
        except (OSError, ValueError, KeyError, json.JSONDecodeError, TypeError):
            oversize.append((name, None, None))
    return oversize


def format_oversized_train_maps_message(oversized, max_dim=MAX_TRAIN_MAP_DIM):
    lines = []
    for name, w, h in oversized:
        if w is None:
            lines.append("%s (không đọc được file)" % name)
        else:
            lines.append("%s (%dx%d)" % (name, w, h))
    body = "\n".join(lines)
    return (
        "Không thể train: mọi map trong map/train phải tối đa %dx%d.\n\n"
        "Các map vượt giới hạn:\n%s" % (max_dim, max_dim, body)
    )


def build_sim_map(spec):
    """Load a JSON spec into a sim_map dict for train/infer."""
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


def _json_in_dir(directory):
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().endswith(".json")
    )


def _merge_by_name(*path_lists):
    by_name = {}
    for paths in path_lists:
        for path in paths:
            by_name[os.path.basename(path).lower()] = path
    return [by_name[name] for name in sorted(by_name)]


def list_map_files(kind=None):
    """List train/infer JSON maps. Bundled infer maps are read-only."""
    ensure_maps_dir("train")
    ensure_maps_dir("infer")

    train_paths = _json_in_dir(TRAIN_MAPS_DIR)
    bundled_infer_paths = _json_in_dir(BUNDLED_INFER_MAPS_DIR)
    external_infer_paths = _json_in_dir(INFER_MAPS_DIR)
    infer_paths = _merge_by_name(bundled_infer_paths, external_infer_paths)

    if kind == "train":
        return train_paths
    if kind == "infer":
        return infer_paths
    return train_paths + infer_paths


def maps_storage_snapshot():
    """Fingerprint map folders so UI can detect external save/delete changes."""
    out = []
    for kind, directories in (
        ("train", (TRAIN_MAPS_DIR,)),
        ("infer", (BUNDLED_INFER_MAPS_DIR, INFER_MAPS_DIR)),
    ):
        entries = []
        for directory in directories:
            if not os.path.isdir(directory):
                continue
            source = "bundled" if _is_same_path(directory, BUNDLED_INFER_MAPS_DIR) else "external"
            for name in sorted(os.listdir(directory)):
                if not name.lower().endswith(".json"):
                    continue
                path = os.path.join(directory, name)
                try:
                    entries.append((source, name, os.path.getmtime(path), os.path.getsize(path)))
                except OSError:
                    entries.append((source, name, 0, 0))
        out.append((kind, tuple(entries)))
    return tuple(out)