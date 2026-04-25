"""preflight.py の live integration: 実 osascript で Kindle 状態を確認する。"""

import pytest

from kindle_cap.preflight import (
    _can_send_keystrokes,
    _has_kindle_window,
    _is_kindle_running,
    preflight,
)


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
