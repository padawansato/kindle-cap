from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.config import Geometry
from kindle_cap.window import (
    _parse_geometry_output,
    activate_kindle,
    get_window_geometry,
)


# ---------------------------------------------------------------------------
# 純粋関数 _parse_geometry_output：mock なしで境界値を網羅
# ---------------------------------------------------------------------------


def test_parse_geometry_normal_output() -> None:
    assert _parse_geometry_output("0\n31\n1440\n869\n") == Geometry(0, 31, 1440, 869)


def test_parse_geometry_without_trailing_newline() -> None:
    assert _parse_geometry_output("0\n31\n1440\n869") == Geometry(0, 31, 1440, 869)


def test_parse_geometry_strips_whitespace_around_numbers() -> None:
    assert _parse_geometry_output(" 0 \n 31 \n 1440 \n 869 \n") == Geometry(
        0, 31, 1440, 869
    )


def test_parse_geometry_accepts_zero_origin_and_size() -> None:
    assert _parse_geometry_output("0\n0\n0\n0\n") == Geometry(0, 0, 0, 0)


def test_parse_geometry_accepts_negative_origin() -> None:
    # マルチモニタや左端より外側の場合に負の x が返る可能性あり
    assert _parse_geometry_output("-100\n-50\n1440\n869\n") == Geometry(
        -100, -50, 1440, 869
    )


def test_parse_geometry_accepts_very_large_values() -> None:
    assert _parse_geometry_output("5000\n5000\n10000\n10000\n") == Geometry(
        5000, 5000, 10000, 10000
    )


def test_parse_geometry_rejects_empty_string() -> None:
    with pytest.raises(RuntimeError, match="unexpected"):
        _parse_geometry_output("")


def test_parse_geometry_rejects_only_newlines() -> None:
    with pytest.raises(RuntimeError, match="unexpected"):
        _parse_geometry_output("\n\n\n\n")


def test_parse_geometry_rejects_too_few_parts() -> None:
    with pytest.raises(RuntimeError, match="unexpected"):
        _parse_geometry_output("1\n2\n3\n")


def test_parse_geometry_rejects_too_many_parts() -> None:
    with pytest.raises(RuntimeError, match="unexpected"):
        _parse_geometry_output("1\n2\n3\n4\n5\n")


def test_parse_geometry_rejects_non_numeric() -> None:
    with pytest.raises(RuntimeError, match="parse"):
        _parse_geometry_output("garbage\n31\n1440\n869\n")


def test_parse_geometry_rejects_float_values() -> None:
    with pytest.raises(RuntimeError, match="parse"):
        _parse_geometry_output("0\n31.5\n1440\n869\n")


def test_parse_geometry_rejects_partial_garbage() -> None:
    with pytest.raises(RuntimeError, match="parse"):
        _parse_geometry_output("0\n31\nNaN\n869\n")


def test_parse_geometry_rejects_empty_part_in_middle() -> None:
    with pytest.raises(RuntimeError, match="parse"):
        _parse_geometry_output("0\n\n1440\n869\n")


def test_parse_geometry_rejects_whitespace_only_part() -> None:
    with pytest.raises(RuntimeError, match="parse"):
        _parse_geometry_output("0\n   \n1440\n869\n")


# ---------------------------------------------------------------------------
# 薄いラッパー activate_kindle / get_window_geometry：subprocess 引数の検証
# （mock を使うのは引数文字列の確認に限る。挙動の検証は live integration 側で行う）
# ---------------------------------------------------------------------------


@patch("kindle_cap.window.subprocess.run")
def test_activate_kindle_calls_osascript_with_amazon_kindle(mock_run: MagicMock) -> None:
    activate_kindle()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert cmd[1] == "-e"
    assert "Amazon Kindle" in cmd[2]
    assert "activate" in cmd[2]
    assert mock_run.call_args.kwargs.get("check") is True


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_targets_kindle_process(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="0\n0\n100\n100\n")
    get_window_geometry()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert "Kindle" in cmd[2]


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_returns_parsed_geometry(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="10\n20\n300\n400\n")
    assert get_window_geometry() == Geometry(10, 20, 300, 400)


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_propagates_parse_error(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="garbage\n")
    with pytest.raises(RuntimeError):
        get_window_geometry()
