from pathlib import Path
from unittest.mock import MagicMock, patch

from kindle_cap.capture import capture_rect
from kindle_cap.config import Geometry


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_invokes_screencapture(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=31, width=1440, height=869)
    out = tmp_path / "page.png"
    capture_rect(geom, out)
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "screencapture"
    assert kwargs.get("check") is True


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_correct_R_argument(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=10, y=20, width=300, height=400)
    out = tmp_path / "p.png"
    capture_rect(geom, out)
    cmd = mock_run.call_args[0][0]
    r_index = cmd.index("-R")
    assert cmd[r_index + 1] == "10,20,300,400"


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_silent_flag(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=0, width=100, height=100)
    capture_rect(geom, tmp_path / "p.png")
    cmd = mock_run.call_args[0][0]
    assert "-x" in cmd


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_output_path(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=0, width=100, height=100)
    out = tmp_path / "p.png"
    capture_rect(geom, out)
    cmd = mock_run.call_args[0][0]
    assert str(out) in cmd
