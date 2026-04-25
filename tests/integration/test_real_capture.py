"""手動 integration テスト。

実行方法:
  1. Kindle.app を起動し、任意の書籍を 1 ページ目で開く
  2. システム設定 > アクセシビリティ で iTerm2 等のターミナルを許可
  3. `uv run pytest -m live -v` を実行
"""
from pathlib import Path

import pytest

from kindle_cap.config import CaptureConfig, Direction
from kindle_cap.orchestrator import run


@pytest.mark.live
def test_capture_two_pages_real(tmp_path: Path) -> None:
    config = CaptureConfig(
        name="live-test",
        pages=2,
        direction=Direction.RTL,
        wait=1.5,
        out=tmp_path,
        keep_png=True,
    )
    run(config)
    out_dir = tmp_path / "live-test"
    assert (out_dir / "page_001.png").exists()
    assert (out_dir / "page_002.png").exists()
    assert (tmp_path / "live-test.pdf").exists()
    assert (tmp_path / "live-test.pdf").stat().st_size > 1000
