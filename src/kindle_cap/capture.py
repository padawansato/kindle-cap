"""Capture a screen rectangle using macOS screencapture."""

import subprocess
from pathlib import Path

from PIL import Image

from .config import Geometry


def _build_screencapture_args(geom: Geometry, out_path: Path) -> list[str]:
    rect = f"{geom.x},{geom.y},{geom.width},{geom.height}"
    return ["screencapture", "-R", rect, "-x", str(out_path)]


def _flatten_alpha(path: Path) -> None:
    img = Image.open(path)
    if img.mode == "RGB":
        return
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        bg.save(path)
        return
    img.convert("RGB").save(path)


def capture_rect(geom: Geometry, out_path: Path) -> None:
    subprocess.run(
        _build_screencapture_args(geom, out_path),
        check=True,
    )
    _flatten_alpha(out_path)
