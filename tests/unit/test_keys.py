import logging
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.config import Direction
from kindle_cap.keys import (
    KeystrokeError,
    _build_keystroke_script,
    _key_code_for,
    send_next_page,
)

# ---------------------------------------------------------------------------
# 純粋関数 _key_code_for: macOS の virtual key code を direction から決める
# ---------------------------------------------------------------------------


def test_key_code_for_rtl_is_right_arrow() -> None:
    assert _key_code_for(Direction.RTL) == 124


def test_key_code_for_ltr_is_left_arrow() -> None:
    assert _key_code_for(Direction.LTR) == 123


def test_key_code_for_all_directions_distinct() -> None:
    """direction 同士で同じ key code を返さないこと"""
    codes = {_key_code_for(d) for d in Direction}
    assert len(codes) == len(Direction)


# ---------------------------------------------------------------------------
# 純粋関数 _build_keystroke_script: AppleScript 文字列を組み立てる
# ---------------------------------------------------------------------------


def test_build_keystroke_script_includes_key_code() -> None:
    script = _build_keystroke_script(124)
    assert "key code 124" in script


def test_build_keystroke_script_targets_kindle_process() -> None:
    script = _build_keystroke_script(124)
    assert 'process "Kindle"' in script


def test_build_keystroke_script_uses_system_events() -> None:
    script = _build_keystroke_script(124)
    assert "System Events" in script


def test_build_keystroke_script_with_left_arrow_code() -> None:
    script = _build_keystroke_script(123)
    assert "key code 123" in script
    assert "key code 124" not in script


@pytest.mark.parametrize("code", [0, 1, 36, 49, 123, 124, 125, 126])
def test_build_keystroke_script_accepts_various_codes(code: int) -> None:
    script = _build_keystroke_script(code)
    assert f"key code {code}" in script


# ---------------------------------------------------------------------------
# 薄いラッパー send_next_page: subprocess 引数の検証は最小限
# 実際のキー送信は live integration で確認する
# ---------------------------------------------------------------------------


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_rtl_passes_right_arrow_script(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert "key code 124" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_ltr_passes_left_arrow_script(mock_run: MagicMock) -> None:
    send_next_page(Direction.LTR)
    cmd = mock_run.call_args[0][0]
    assert "key code 123" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_uses_check_true(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    assert mock_run.call_args.kwargs.get("check") is True


# ---------------------------------------------------------------------------
# CalledProcessError → custom exception ラップ + logger (issue #62)
# ---------------------------------------------------------------------------


def _make_called_process_error(
    stderr: str | None, returncode: int = 1
) -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(
        returncode=returncode,
        cmd=["osascript", "-e", "..."],
        output="",
        stderr=stderr,
    )


def test_keystroke_error_is_runtime_error_subclass() -> None:
    assert issubclass(KeystrokeError, RuntimeError)


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_captures_output(mock_run: MagicMock) -> None:
    """既存挙動からの変更点として、capture_output=True が指定される。"""
    send_next_page(Direction.RTL)
    assert mock_run.call_args.kwargs.get("capture_output") is True
    assert mock_run.call_args.kwargs.get("text") is True


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_wraps_called_process_error_with_stderr(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = _make_called_process_error(
        "execution error: process Kindle isn't running (-1719)"
    )
    with pytest.raises(KeystrokeError, match="isn't running"):
        send_next_page(Direction.RTL)


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_includes_exit_code_in_message(mock_run: MagicMock) -> None:
    mock_run.side_effect = _make_called_process_error("err", returncode=2)
    with pytest.raises(KeystrokeError, match="exit 2"):
        send_next_page(Direction.RTL)


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_handles_empty_stderr(mock_run: MagicMock) -> None:
    mock_run.side_effect = _make_called_process_error("")
    with pytest.raises(KeystrokeError, match="no stderr"):
        send_next_page(Direction.RTL)


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_handles_none_stderr(mock_run: MagicMock) -> None:
    mock_run.side_effect = _make_called_process_error(None)
    with pytest.raises(KeystrokeError, match="no stderr"):
        send_next_page(Direction.RTL)


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_logs_error_on_failure(
    mock_run: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_run.side_effect = _make_called_process_error("keystroke oops")
    caplog.set_level(logging.ERROR, logger="kindle_cap")
    with pytest.raises(KeystrokeError):
        send_next_page(Direction.RTL)
    assert "keystroke osascript failed" in caplog.text
    assert "keystroke oops" in caplog.text
