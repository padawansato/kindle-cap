"""capture.py の live integration: 実 screencapture を叩いて PNG を生成する。

Kindle 不要 — 任意の画面領域を撮るだけなので Kindle が起動していなくても動く
（live マーカーを付けているのは GUI セッション必須のため）。

【マルチディスプレイ対応の手動確認】
- 外部ディスプレイの座標で Geometry を作って capture_rect を呼ぶと、
  該当ディスプレイの内容が PNG として保存される
- 例: 右に接続した外部 1920x1080 なら Geometry(1440, 0, 1920, 1080) で撮影可能
"""

from pathlib import Path

import pytest
from PIL import Image

from kindle_cap.capture import capture_rect
from kindle_cap.config import Geometry


@pytest.mark.live
def test_real_capture_creates_png_file(tmp_path: Path) -> None:
    out = tmp_path / "shot.png"
    capture_rect(Geometry(0, 0, 100, 100), out)
    assert out.exists()
    assert out.stat().st_size > 0


@pytest.mark.live
def test_real_capture_writes_rgb_mode_png(tmp_path: Path) -> None:
    """flatten を経て RGB モードになっていること（アルファチャンネル除去）"""
    out = tmp_path / "shot.png"
    capture_rect(Geometry(0, 0, 100, 100), out)
    assert Image.open(out).mode == "RGB"


@pytest.mark.live
def test_real_capture_size_matches_geometry_or_retina_double(tmp_path: Path) -> None:
    """論理サイズ x 1 か x 2（Retina）のどちらかになっていること"""
    out = tmp_path / "shot.png"
    capture_rect(Geometry(0, 0, 100, 80), out)
    img = Image.open(out)
    w, h = img.size
    assert w in (100, 200), f"width {w} は 100 でも 200 でもない"
    assert h in (80, 160), f"height {h} は 80 でも 160 でもない"
    # 縦横比は維持される
    assert (w / h) == pytest.approx(100 / 80, rel=0.01)


@pytest.mark.live
def test_real_capture_different_geometries_produce_different_pngs(tmp_path: Path) -> None:
    """異なる位置を撮ると内容が違うこと（座標が無視されていないこと）"""
    p1 = tmp_path / "p1.png"
    p2 = tmp_path / "p2.png"
    capture_rect(Geometry(0, 0, 50, 50), p1)
    capture_rect(Geometry(500, 500, 50, 50), p2)
    assert p1.read_bytes() != p2.read_bytes()


@pytest.mark.live
def test_real_capture_overwrites_existing_file(tmp_path: Path) -> None:
    out = tmp_path / "shot.png"
    out.write_bytes(b"old garbage")  # 既存ダミー
    capture_rect(Geometry(0, 0, 50, 50), out)
    # PNG の魔数で上書きを確認
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
