#!/usr/bin/env python3
"""
Build state_lookup.py thành file exe độc lập.

Usage:
    python build_state_lookup_exe.py
    python build_state_lookup_exe.py --clean-only
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
MAIN = ROOT / "state_lookup.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "state-lookup"
SPEC = ROOT / "StateLookup.spec"

APP_ICON_PNG = ROOT / "assets" / "find.png"
APP_ICON_ICO = ROOT / "assets" / "find.ico"
GENERATED_ICON_DIR = BUILD / "icons"
GENERATED_ICO = GENERATED_ICON_DIR / "find.ico"

DEFAULT_NAME = "StateLookup"


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
    _remove(SPEC)
    exe = DIST / f"{DEFAULT_NAME}.exe"
    if exe.is_file():
        _remove(exe)


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


def _ensure_pillow():
    try:
        import PIL  # noqa: F401
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


def _windows_icon() -> Optional[Path]:
    if not APP_ICON_PNG.is_file():
        return None
    if APP_ICON_ICO.is_file():
        return APP_ICON_ICO
    icon = _write_ico_from_png(APP_ICON_PNG, GENERATED_ICO)
    try:
        shutil.copy2(icon, APP_ICON_ICO)
    except OSError:
        pass
    return icon


def build(name: str) -> Path:
    if not MAIN.is_file():
        raise FileNotFoundError(f"Missing entrypoint: {MAIN}")
    if os.name != "nt":
        raise BuildError("StateLookup exe build chỉ hỗ trợ Windows.")
    if not _pyinstaller_available():
        raise BuildError(
            "PyInstaller chưa cài.\n"
            f"Cài bằng: {sys.executable} -m pip install pyinstaller"
        )

    clean()
    sep = ";"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        name,
        "--paths",
        str(ROOT / "libs"),
        "--hidden-import",
        "bootstrap",
        "--hidden-import",
        "RL_lib.rl_core",
        "--hidden-import",
        "RL_lib.state_codec",
        "--hidden-import",
        "RL_lib.grid",
        "--add-data",
        f"{ROOT / 'libs'}{sep}libs",
        "--add-data",
        f"{ROOT / 'assets'}{sep}assets",
    ]

    icon = _windows_icon()
    if icon:
        command.extend(["--icon", str(icon)])

    command.append(str(MAIN))
    _run(command)
    return DIST / f"{name}.exe"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build StateLookup exe.")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Tên file exe.")
    parser.add_argument("--clean-only", action="store_true", help="Xóa artifact build.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.clean_only:
        clean()
        print("Cleaned build artifacts.")
        return 0
    try:
        output = build(name=args.name)
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    print()
    print("Build complete:")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
