import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.preflight import PreflightError, preflight


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
def test_preflight_raises_when_accessibility_denied(mock_run: MagicMock) -> None:
    err = subprocess.CalledProcessError(1, "osascript", stderr="error -1719: Not authorized")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(PreflightError, match="アクセシビリティ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_propagates_unknown_subprocess_error(mock_run: MagicMock) -> None:
    err = subprocess.CalledProcessError(2, "osascript", stderr="something else")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(subprocess.CalledProcessError):
        preflight()
