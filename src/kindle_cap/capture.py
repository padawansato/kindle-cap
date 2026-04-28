"""Capture a screen rectangle using macOS screencapture."""

import subprocess
from pathlib import Path

from PIL import Image

from .config import Geometry


class CaptureError(RuntimeError):
    pass


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
    # macOS の screencapture は書き込み失敗時でも exit 0 で抜けることがあるため、
    # check=True に頼らず out_path の存在を確認する。stderr は診断のため捕捉する。
    result = subprocess.run(
        _build_screencapture_args(geom, out_path),
        check=True,
        capture_output=True,
        text=True,
    )
    if not out_path.exists():
        stderr_text = (result.stderr or "").strip() or "(no stderr)"
        raise CaptureError(f"screencapture exited 0 but did not create {out_path}: {stderr_text}")
    _flatten_alpha(out_path)
