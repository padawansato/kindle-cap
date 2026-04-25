"""Capture a screen rectangle using macOS screencapture."""
import subprocess
from pathlib import Path

from .config import Geometry


def capture_rect(geom: Geometry, out_path: Path) -> None:
    rect = f"{geom.x},{geom.y},{geom.width},{geom.height}"
    subprocess.run(
        ["screencapture", "-R", rect, "-x", str(out_path)],
        check=True,
    )
