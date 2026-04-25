"""Tests for library auto-switch functionality."""
from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.config import Geometry
from kindle_cap.library import (
    back_to_library,
    click_at,
    close_book,
    compute_book_positions,
)


# ---------------------------------------------------------------------------
# 純粋関数 compute_book_positions: ライブラリのグリッド座標を計算
# ---------------------------------------------------------------------------


def test_compute_positions_returns_non_empty() -> None:
    geom = Geometry(0, 0, 1440, 869)
    assert len(compute_book_positions(geom, n_cols=6)) > 0


def test_compute_positions_all_inside_window() -> None:
    geom = Geometry(0, 0, 1440, 869)
    for x, y in compute_book_positions(geom, n_cols=6):
        assert 0 <= x <= 1440
        assert 0 <= y <= 869


def test_compute_positions_count_is_multiple_of_n_cols() -> None:
    geom = Geometry(0, 0, 1440, 869)
    positions = compute_book_positions(geom, n_cols=6)
    assert len(positions) % 6 == 0


def test_compute_positions_first_two_are_same_row_different_x() -> None:
    geom = Geometry(0, 0, 1440, 869)
    positions = compute_book_positions(geom, n_cols=6)
    x1, y1 = positions[0]
    x2, y2 = positions[1]
    assert y1 == y2  # 同じ行
    assert x2 > x1  # 右方向


def test_compute_positions_row_break_at_n_cols() -> None:
    geom = Geometry(0, 0, 1440, 869)
    positions = compute_book_positions(geom, n_cols=6)
    if len(positions) >= 7:
        x1, y1 = positions[0]
        x7, y7 = positions[6]
        assert y7 > y1  # 次の行
        assert x7 == x1  # 同じ列の x


def test_compute_positions_respects_window_offset() -> None:
    """外部ディスプレイにウィンドウがある場合 (x>0, y>0)"""
    geom = Geometry(310, 1111, 1440, 869)
    positions = compute_book_positions(geom, n_cols=6)
    for x, y in positions:
        assert x >= 310
        assert y >= 1111
        assert x < 310 + 1440
        assert y < 1111 + 869


def test_compute_positions_respects_negative_window_offset() -> None:
    """マルチディスプレイ（外部モニタが左に配置）: x が負"""
    geom = Geometry(-1920, 0, 1920, 1080)
    positions = compute_book_positions(geom, n_cols=6)
    for x, y in positions:
        assert -1920 <= x < 0


def test_compute_positions_n_cols_3_vs_6_same_window() -> None:
    geom = Geometry(0, 0, 1440, 869)
    p3 = compute_book_positions(geom, n_cols=3)
    p6 = compute_book_positions(geom, n_cols=6)
    rows_3 = len(p3) // 3
    rows_6 = len(p6) // 6
    assert rows_3 == rows_6
    assert len(p6) == 2 * len(p3)


def test_compute_positions_n_cols_zero_rejected() -> None:
    geom = Geometry(0, 0, 1440, 869)
    with pytest.raises(ValueError, match="n_cols"):
        compute_book_positions(geom, n_cols=0)


def test_compute_positions_n_cols_negative_rejected() -> None:
    geom = Geometry(0, 0, 1440, 869)
    with pytest.raises(ValueError, match="n_cols"):
        compute_book_positions(geom, n_cols=-1)


def test_compute_positions_too_narrow_window_rejected() -> None:
    """パディング合計 > 幅 ならエラー"""
    geom = Geometry(0, 0, 50, 869)
    with pytest.raises(ValueError):
        compute_book_positions(geom, n_cols=6, left_padding=30, right_padding=30)


def test_compute_positions_short_window_returns_empty_list() -> None:
    """高さが足りなくて 1 行分も入らないなら空"""
    geom = Geometry(0, 0, 1440, 100)
    positions = compute_book_positions(
        geom, n_cols=6, top_padding=80, bottom_padding=50, row_height=240
    )
    assert positions == []


def test_compute_positions_first_cell_is_within_top_padding_band() -> None:
    """1行目の y は top_padding より下、かつ row_height より上"""
    geom = Geometry(0, 0, 1440, 869)
    positions = compute_book_positions(
        geom, n_cols=6, top_padding=80, row_height=240
    )
    _, y_first = positions[0]
    assert y_first >= 80
    assert y_first < 80 + 240


def test_compute_positions_first_cell_is_within_left_padding_band() -> None:
    """1列目の x は left_padding より右、cell_width 内"""
    geom = Geometry(0, 0, 1440, 869)
    positions = compute_book_positions(
        geom, n_cols=6, left_padding=30, right_padding=30
    )
    x_first, _ = positions[0]
    cell_width = (1440 - 60) / 6
    assert x_first >= 30
    assert x_first < 30 + cell_width


# ---------------------------------------------------------------------------
# 薄ラッパー click_at / close_book / back_to_library
# ---------------------------------------------------------------------------


@patch("kindle_cap.library.subprocess.run")
def test_click_at_invokes_osascript_with_coords(mock_run: MagicMock) -> None:
    click_at(123, 456)
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert cmd[1] == "-e"
    assert "{123, 456}" in cmd[2]
    assert "click at" in cmd[2]


@patch("kindle_cap.library.subprocess.run")
def test_click_at_targets_kindle_process(mock_run: MagicMock) -> None:
    click_at(0, 0)
    cmd = mock_run.call_args[0][0]
    assert 'process "Kindle"' in cmd[2]


@patch("kindle_cap.library.subprocess.run")
def test_click_at_uses_check_true(mock_run: MagicMock) -> None:
    click_at(100, 100)
    assert mock_run.call_args.kwargs.get("check") is True


@patch("kindle_cap.library.subprocess.run")
def test_click_at_handles_negative_coords(mock_run: MagicMock) -> None:
    """マルチディスプレイ環境で負の座標もそのまま渡す"""
    click_at(-1500, -200)
    cmd = mock_run.call_args[0][0]
    assert "{-1500, -200}" in cmd[2]


@patch("kindle_cap.library.subprocess.run")
def test_close_book_sends_cmd_w(mock_run: MagicMock) -> None:
    close_book()
    cmd = mock_run.call_args[0][0]
    assert 'keystroke "w"' in cmd[2]
    assert "command down" in cmd[2]
    assert 'process "Kindle"' in cmd[2]


@patch("kindle_cap.library.subprocess.run")
def test_back_to_library_sends_cmd_l(mock_run: MagicMock) -> None:
    back_to_library()
    cmd = mock_run.call_args[0][0]
    assert 'keystroke "l"' in cmd[2]
    assert "command down" in cmd[2]
