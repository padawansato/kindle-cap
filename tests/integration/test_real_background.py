"""手動 integration テスト (issue #84): Kindle を前面に出さずに撮る。

実行方法:
  1. Kindle.app で任意の書籍を開き、別のアプリ (ターミナルなど) を前面にする
  2. `uv run pytest -m live tests/integration/test_real_background.py -v`
"""

from pathlib import Path

import pytest
from PIL import Image

from kindle_cap.background import capture_kindle_window, kindle_window


@pytest.mark.live
def test_capture_kindle_window_while_another_app_is_frontmost(tmp_path: Path) -> None:
    win = kindle_window()
    assert win is not None and win.onscreen
    out = tmp_path / "bg.png"
    assert capture_kindle_window(out, crop_top=28) is True
    img = Image.open(out)
    assert img.mode == "RGB"
    # Retina なら窓の 2 倍。crop_top ぶん高さが減っている
    scale = img.width / win.width
    assert abs(img.height - (win.height - 28) * scale) <= scale
