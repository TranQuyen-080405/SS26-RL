#!/usr/bin/env python3
"""
Build state_lookup.py thành app desktop độc lập.

Usage:
    python build_state_lookup_exe.py
    python build_state_lookup_exe.py --target app
    python build_state_lookup_exe.py --target exe
    python build_state_lookup_exe.py --clean-only

Mặc định: macOS → dist/StateLookup.app, Windows → dist/StateLookup.exe.
PyInstaller không cross-compile — build .app trên macOS, .exe trên Windows.
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
GENERATED_ICNS = GENERATED_ICON_DIR / "find.icns"

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


def _data_sep() -> str:
    return ";" if os.name == "nt" else ":"


def clean(name: str = DEFAULT_NAME) -> None:
    _remove(BUILD)
    _remove(SPEC)
    _remove(DIST / f"{name}.exe")
    _remove(DIST / f"{name}.app")


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


def _mac_icon_from_png() -> Optional[Path]:
    if sys.platform != "darwin" or not APP_ICON_PNG.is_file():
        return None
    iconset = GENERATED_ICON_DIR / "find.iconset"
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


def _icon_arg(target: str) -> list[str]:
    if target == "app":
        icon = _mac_icon_from_png()
        return ["--icon", str(icon)] if icon else []
    icon = _windows_icon()
    return ["--icon", str(icon)] if icon else []


def build(name: str, target: str) -> Path:
    if not MAIN.is_file():
        raise FileNotFoundError(f"Missing entrypoint: {MAIN}")
    if not _pyinstaller_available():
        raise BuildError(
            "PyInstaller chưa cài.\n"
            f"Cài bằng: {sys.executable} -m pip install pyinstaller"
        )

    resolved_target = _resolve_target(target)
    clean(name=name)
    sep = _data_sep()

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

    if resolved_target == "app":
        command.extend(["--onedir", "--windowed"])
    else:
        command.extend(["--onefile", "--windowed"])

    command.extend(_icon_arg(resolved_target))
    command.append(str(MAIN))
    _run(command)

    if resolved_target == "app":
        return DIST / f"{name}.app"
    return DIST / f"{name}.exe"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build StateLookup desktop app.")
    parser.add_argument(
        "--target",
        choices=("auto", "app", "exe"),
        default="auto",
        help="Build target. Default: app on macOS, exe on Windows.",
    )
    parser.add_argument("--name", default=DEFAULT_NAME, help="Tên file app/exe.")
    parser.add_argument("--clean-only", action="store_true", help="Xóa artifact build.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.clean_only:
        clean(name=args.name)
        print("Cleaned build artifacts.")
        return 0
    try:
        output = build(name=args.name, target=args.target)
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    print()
    print("Build complete:")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
