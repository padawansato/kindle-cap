from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.config import Geometry
from kindle_cap.window import activate_kindle, get_window_geometry


@patch("kindle_cap.window.subprocess.run")
def test_activate_kindle_calls_osascript(mock_run: MagicMock) -> None:
    activate_kindle()
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "osascript"
    assert cmd[1] == "-e"
    assert "Amazon Kindle" in cmd[2]
    assert "activate" in cmd[2]
    assert kwargs.get("check") is True


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_parses_newline_output(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="0\n31\n1440\n869\n")
    g = get_window_geometry()
    assert g == Geometry(x=0, y=31, width=1440, height=869)


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_targets_kindle_process(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="0\n0\n100\n100\n")
    get_window_geometry()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert "Kindle" in cmd[2]


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_unexpected_output_raises(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="garbage\n")
    with pytest.raises(RuntimeError, match="output"):
        get_window_geometry()


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_partial_output_raises(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="1\n2\n")
    with pytest.raises(RuntimeError):
        get_window_geometry()
