"""preflight.py の live integration: 実 osascript で Kindle 状態を確認する。"""

from pathlib import Path
from time import sleep

import pytest

from kindle_cap.capture import capture_rect
from kindle_cap.config import Direction
from kindle_cap.keys import send_next_page
from kindle_cap.preflight import (
    _can_send_keystrokes,
    _has_kindle_window,
    _is_kindle_running,
    detect_direction,
    preflight,
)
from kindle_cap.window import activate_kindle, get_window_geometry


@pytest.mark.live
def test_real_is_kindle_running_returns_true_when_app_open() -> None:
    """Kindle が起動している前提なので True が返るべき"""
    assert _is_kindle_running() is True


@pytest.mark.live
def test_real_has_kindle_window_returns_true_when_window_open() -> None:
    assert _has_kindle_window() is True


@pytest.mark.live
def test_real_can_send_keystrokes_returns_true_when_authorized() -> None:
    """アクセシビリティ権限が付与されている前提"""
    assert _can_send_keystrokes() is True


@pytest.mark.live
def test_real_preflight_passes_with_running_kindle() -> None:
    preflight()  # 例外が出ないこと


@pytest.mark.live
def test_real_detect_direction_returns_a_direction(tmp_path: Path) -> None:
    """実機 Kindle で detect_direction を実行し、Direction が返ることを確認。

    前提: Kindle.app 起動済み・書籍が表紙ページで開かれている。
    本テストは実際にページを送るので、実行後は表紙から probe_count 枚進んだ
    位置になっている可能性がある（手動で表紙に戻すこと）。
    """
    direction, pngs = detect_direction(
        out_dir=tmp_path,
        geom_provider=get_window_geometry,
        activator=activate_kindle,
        capturer=capture_rect,
        sender=send_next_page,
        sleeper=sleep,
        wait=1.5,
    )
    assert direction in (Direction.RTL, Direction.LTR)
    # 試写流用 (3 枚) または fallback (空) のいずれか
    assert len(pngs) in (0, 3)
    if pngs:
        for p in pngs:
            assert p.exists()
            assert p.stat().st_size > 0
