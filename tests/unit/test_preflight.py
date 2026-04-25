import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.preflight import (
    PreflightError,
    _is_accessibility_error,
    _parse_count,
    preflight,
)


# ---------------------------------------------------------------------------
# 純粋関数 _parse_count: "1\n" → 1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("0", 0),
    ("1", 1),
    ("10", 10),
    ("999", 999),
    ("0\n", 0),
    ("1\n", 1),
    (" 5 ", 5),
    ("\n5\n", 5),
])
def test_parse_count_extracts_integer(text: str, expected: int) -> None:
    assert _parse_count(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "1.5", "one", "  ", "\n\n"])
def test_parse_count_rejects_non_integer(text: str) -> None:
    with pytest.raises(ValueError):
        _parse_count(text)


# ---------------------------------------------------------------------------
# 純粋関数 _is_accessibility_error: stderr 文字列 → 権限エラーか判定
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stderr", [
    "error: -1719 (not authorized)",
    "execution error: -1719",
    "Some prefix -1719 some suffix",
    "not allowed assistive access",
    "Application is not allowed assistive access",
])
def test_is_accessibility_error_recognizes_known_patterns(stderr: str) -> None:
    assert _is_accessibility_error(stderr) is True


@pytest.mark.parametrize("stderr", [
    "",
    "Some other error",
    "syntax error",
    "process not found",
    "-1718",  # 似た番号
    "1719",  # マイナスなし
])
def test_is_accessibility_error_returns_false_for_other_errors(stderr: str) -> None:
    assert _is_accessibility_error(stderr) is False


def test_is_accessibility_error_handles_none_safely() -> None:
    """stderr が None を渡されても True/False を返すべき"""
    assert _is_accessibility_error(None) is False


# ---------------------------------------------------------------------------
# preflight: シーケンスを subprocess mock で検証
# 各シナリオごとに 1 つずつ
# ---------------------------------------------------------------------------


def _run_factory(outputs: list):
    """outputs は呼び出し順に返す stdout (str) または raise する例外のリスト"""
    iterator = iter(outputs)

    def _run(*args, **kwargs):
        item = next(iterator)
        if isinstance(item, BaseException):
            raise item
        return MagicMock(stdout=item)

    return _run


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_passes_when_all_ok(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["1\n", "1\n", "Finder\n"])
    preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_kindle_not_running(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["0\n"])
    with pytest.raises(PreflightError, match="Kindle"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_no_window(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["1\n", "0\n"])
    with pytest.raises(PreflightError, match="ウィンドウ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_accessibility_denied_with_dash_1719(
    mock_run: MagicMock,
) -> None:
    err = subprocess.CalledProcessError(1, "osascript", stderr="error -1719: Not authorized")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(PreflightError, match="アクセシビリティ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_accessibility_denied_with_text_pattern(
    mock_run: MagicMock,
) -> None:
    err = subprocess.CalledProcessError(
        1, "osascript", stderr="not allowed assistive access"
    )
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(PreflightError, match="アクセシビリティ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_propagates_unknown_subprocess_error(mock_run: MagicMock) -> None:
    err = subprocess.CalledProcessError(2, "osascript", stderr="something else")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(subprocess.CalledProcessError):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_calls_three_subprocesses_when_all_ok(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["1\n", "1\n", "Finder\n"])
    preflight()
    assert mock_run.call_count == 3


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_short_circuits_on_kindle_missing(mock_run: MagicMock) -> None:
    """Kindle 未起動なら、後続の osascript は呼ばれないこと"""
    mock_run.side_effect = _run_factory(["0\n"])
    with pytest.raises(PreflightError):
        preflight()
    assert mock_run.call_count == 1
