"""Capture a screen rectangle using macOS screencapture."""

import logging
import subprocess
from pathlib import Path

from PIL import Image

from .config import Geometry

logger = logging.getLogger(__name__)


class CaptureError(RuntimeError):
    pass


def crop_top(geom: Geometry, points: int) -> Geometry:
    """撮影矩形の上端を `points` (論理ポイント) だけ削った Geometry を返す。

    System Events が返すウィンドウ frame はタイトルバー (信号機ボタン) を含むため、
    固定型書籍ではページ画像の上端にボタンが写り込む (issue #69)。screencapture -R は
    論理座標を取るので、Retina でも points はそのまま渡せる。
    """
    if points < 0:
        raise ValueError(f"crop_top must be >= 0 (got {points})")
    if points >= geom.height:
        raise ValueError(
            f"crop_top must be smaller than window height (crop_top={points}, height={geom.height})"
        )
    if points == 0:
        return geom
    return Geometry(x=geom.x, y=geom.y + points, width=geom.width, height=geom.height - points)


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
    args = _build_screencapture_args(geom, out_path)
    logger.debug("screencapture: %s", " ".join(args))
    # macOS の screencapture は書き込み失敗時でも exit 0 で抜けることがあるため、
    # check=True に頼らず out_path の存在を確認する。stderr は診断のため捕捉する。
    result = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
    )
    if not out_path.exists():
        stderr_text = (result.stderr or "").strip() or "(no stderr)"
        logger.error(
            "screencapture succeeded but file missing: %s (stderr: %s)",
            out_path,
            stderr_text,
        )
        raise CaptureError(f"screencapture exited 0 but did not create {out_path}: {stderr_text}")
    _flatten_alpha(out_path)
