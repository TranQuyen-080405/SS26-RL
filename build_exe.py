#!/usr/bin/env python3
"""
Build SS26-RL into a fresh desktop bundle.

Usage:
    python build_exe.py

Optional:
    python build_exe.py --target app
    python build_exe.py --target exe
    python build_exe.py --name SS26-RL-dev
    python build_exe.py --onedir
    python build_exe.py --console
    python build_exe.py --clean-only
    python build_exe.py --exclude-infer-maps

Default target is native: macOS builds dist/SS26-RL.app, Windows builds
dist/SS26-RL.exe. PyInstaller cannot cross-compile, so build the .app on macOS
and the .exe on Windows.

By default, map/infer is bundled into the app/exe as read-only data.
Extra maps saved by users still live next to the built app/exe.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "SS26-RL.spec"
APP_ICON_PNG = ROOT / "assets" / "icon_app.png"
APP_ICON_ICO = ROOT / "assets" / "icon_app.ico"
GENERATED_ICON_DIR = BUILD / "icons"
GENERATED_ICNS = GENERATED_ICON_DIR / "icon_app.icns"
GENERATED_ICO = GENERATED_ICON_DIR / "icon_app.ico"

DEFAULT_NAME = "SS26-RL"
DATA_PATHS = (
    "libs",
    "checkpoints",
    "reward_formula",
    "assets",
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
    "app_icon",
)
COLLECT_ALL = (
    "bleak",
)


class BuildError(RuntimeError):
    pass


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


def _native_target() -> str:
    if sys.platform == "darwin":
        return "app"
    if os.name == "nt":
        return "exe"
    raise BuildError("Auto target supports macOS (.app) and Windows (.exe) only.")


def _resolve_target(target: str) -> str:
    resolved = _native_target() if target == "auto" else target
    if resolved == "app" and sys.platform != "darwin":
        raise BuildError(".app builds must be run on macOS.")
    if resolved == "exe" and os.name != "nt":
        raise BuildError(".exe builds must be run on Windows.")
    return resolved


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


def _ensure_pillow():
    try:
        import PIL  # noqa: F401
        return
    except ImportError:
        print("Installing Pillow for icon conversion...")
        _run([sys.executable, "-m", "pip", "install", "pillow"])


def _write_ico_from_png(src: Path, dest: Path) -> Path:
    _ensure_pillow()
    from PIL import Image

    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src)
    if img.mode not in ("RGBA", "RGB"):
        img = img.convert("RGBA")
    img.save(
        dest,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return dest


def _mac_icon_from_png() -> Optional[Path]:
    """Convert assets/icon_app.png to a temporary .icns for PyInstaller on macOS."""
    if sys.platform != "darwin" or not APP_ICON_PNG.is_file():
        return None
    iconset = GENERATED_ICON_DIR / "icon_app.iconset"
    _remove(iconset)
    GENERATED_ICON_DIR.mkdir(parents=True, exist_ok=True)
    iconset.mkdir(parents=True, exist_ok=True)

    sizes = (
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    )
    for size, filename in sizes:
        _run(["sips", "-z", str(size), str(size), str(APP_ICON_PNG), "--out", str(iconset / filename)])
    _remove(GENERATED_ICNS)
    _run(["iconutil", "-c", "icns", str(iconset), "-o", str(GENERATED_ICNS)])
    return GENERATED_ICNS


def _windows_icon_from_png() -> Optional[Path]:
    """Convert assets/icon_app.png to .ico for PyInstaller on Windows."""
    if not APP_ICON_PNG.is_file():
        return None
    try:
        return _write_ico_from_png(APP_ICON_PNG, GENERATED_ICO)
    except Exception as exc:
        print(f"Note: could not build icon from assets/icon_app.png: {exc}")
        return None


def _windows_icon() -> Optional[Path]:
    if APP_ICON_ICO.is_file():
        return APP_ICON_ICO
    icon = _windows_icon_from_png()
    if icon and not APP_ICON_ICO.is_file():
        try:
            shutil.copy2(icon, APP_ICON_ICO)
        except OSError:
            pass
    return icon


def _icon_arg(target: str) -> list[str]:
    if target == "app":
        icon = _mac_icon_from_png()
        return ["--icon", str(icon)] if icon else []
    icon = _windows_icon()
    if icon:
        return ["--icon", str(icon)]
    return []


def build(
    name: str,
    target: str,
    onedir: bool,
    console: bool,
    exclude_infer_maps: bool,
) -> Path:
    if not MAIN.is_file():
        raise FileNotFoundError(f"Missing entrypoint: {MAIN}")
    if not _pyinstaller_available():
        raise BuildError(
            "PyInstaller is not installed for this Python.\n"
            f"Install it with:\n  {sys.executable} -m pip install pyinstaller"
        )

    resolved_target = _resolve_target(target)
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

    if resolved_target == "app":
        command.extend(["--onedir", "--windowed"])
    else:
        command.append("--onedir" if onedir else "--onefile")
        command.append("--console" if console else "--windowed")

    for package in COLLECT_ALL:
        command.extend(["--collect-all", package])
    for module in HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module])

    command.extend(_icon_arg(resolved_target))
    command.extend(_add_data_args(exclude_infer_maps=exclude_infer_maps))
    command.append(str(MAIN))

    _run(command)
    if resolved_target == "app":
        return DIST / f"{name}.app"
    if onedir:
        return DIST / name
    return DIST / f"{name}.exe"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SS26-RL desktop app.")
    parser.add_argument(
        "--target",
        choices=("auto", "app", "exe"),
        default="auto",
        help="Build target. Default: app on macOS, exe on Windows.",
    )
    parser.add_argument("--name", default=DEFAULT_NAME, help="Output app/exe name.")
    parser.add_argument("--onedir", action="store_true", help="For exe target, build a folder app instead of one .exe.")
    parser.add_argument("--console", action="store_true", help="For exe target, keep a console window for logs/debugging.")
    parser.add_argument("--clean-only", action="store_true", help="Remove build artifacts and exit.")
    parser.add_argument(
        "--exclude-infer-maps",
        action="store_true",
        help="Do not bundle map/infer into the app/exe.",
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
            target=args.target,
            onedir=args.onedir,
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
