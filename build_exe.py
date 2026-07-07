#!/usr/bin/env python3
"""
Build SS26-RL into a fresh Windows .exe.

Usage:
    python build_exe.py

Optional:
    python build_exe.py --name SS26-RL-dev
    python build_exe.py --onedir
    python build_exe.py --clean-only
    python build_exe.py --exclude-infer-maps

The script uses PyInstaller and bundles the app entrypoint plus project data
folders needed by the UI. It intentionally excludes build outputs and VCS /
virtualenv folders so repeated builds do not recursively package old artifacts.

By default, map/infer is bundled into the exe as read-only data.
Extra maps saved by users still live next to the exe.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "SS26-RL.spec"

DEFAULT_NAME = "SS26-RL"
DATA_PATHS = (
    "libs",
    "checkpoints",
    "reward_formula",
    "calScore.py",
    "requirements.txt",
)
HIDDEN_IMPORTS = (
    "runtime_paths",
    "rl_runner",
    "train_log",
    "map.map_io",
    "map.sim_map",
    "robot.action",
    "robot.policy_io",
    "robot.robot",
    "robot.robot_map",
    "robot.trainer",
    "RL_lib.reward_config",
    "RL_lib.formula_store",
    "RL_lib.reward_formula",
    "RL_lib.student_formula",
    "Ui_app.create_map_UI",
    "Ui_app.learn_lab_UI",
    "Ui_app.rl_app_UI",
    "app_tabs.shell",
    "app_tabs.robot_monitor",
)
COLLECT_ALL = (
    "bleak",
)


def _run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def clean() -> None:
    _remove(BUILD)
    _remove(DIST)
    _remove(SPEC)
    for spec in ROOT.glob("*.spec"):
        _remove(spec)


def _pyinstaller_available() -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _add_data_args(exclude_infer_maps: bool) -> list[str]:
    args: list[str] = []
    sep = ";" if os.name == "nt" else ":"
    for rel in DATA_PATHS:
        src = ROOT / rel
        if not src.exists():
            continue
        args.extend(["--add-data", f"{src}{sep}{rel}"])

    train_maps = ROOT / "map" / "train"
    if train_maps.exists():
        args.extend(["--add-data", f"{train_maps}{sep}map/train"])

    infer_maps = ROOT / "map" / "infer"
    if not exclude_infer_maps and infer_maps.exists():
        args.extend(["--add-data", f"{infer_maps}{sep}map/infer"])
    return args


def build(name: str, onefile: bool, console: bool, exclude_infer_maps: bool) -> Path:
    if not MAIN.is_file():
        raise FileNotFoundError(f"Missing entrypoint: {MAIN}")
    if not _pyinstaller_available():
        raise RuntimeError(
            "PyInstaller is not installed for this Python.\n"
            f"Install it with:\n  {sys.executable} -m pip install pyinstaller"
        )

    clean()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        name,
        "--paths",
        str(ROOT / "libs"),
        "--paths",
        str(ROOT / "libs" / "Simulation"),
        "--paths",
        str(ROOT / "libs" / "Robot_embbed"),
    ]
    command.append("--onefile" if onefile else "--onedir")
    command.append("--console" if console else "--windowed")

    for package in COLLECT_ALL:
        command.extend(["--collect-all", package])
    for module in HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module])

    command.extend(_add_data_args(exclude_infer_maps=exclude_infer_maps))
    command.append(str(MAIN))

    _run(command)
    return DIST / (f"{name}.exe" if onefile and os.name == "nt" else name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SS26-RL into an .exe.")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Output executable name.")
    parser.add_argument("--onedir", action="store_true", help="Build folder app instead of one .exe.")
    parser.add_argument("--console", action="store_true", help="Keep a console window for logs/debugging.")
    parser.add_argument("--clean-only", action="store_true", help="Remove build artifacts and exit.")
    parser.add_argument(
        "--exclude-infer-maps",
        action="store_true",
        help="Do not bundle map/infer into the exe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.clean_only:
        clean()
        print("Cleaned build artifacts.")
        return 0

    try:
        output = build(
            name=args.name,
            onefile=not args.onedir,
            console=args.console,
            exclude_infer_maps=args.exclude_infer_maps,
        )
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1

    print()
    print("Build complete:")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
