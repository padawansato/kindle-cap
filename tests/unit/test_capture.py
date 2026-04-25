from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from kindle_cap.capture import _flatten_alpha, capture_rect
from kindle_cap.config import Geometry


def _stub_screencapture(out_path: Path, mode: str = "RGBA") -> None:
    """`screencapture` が PNG を作る挙動を再現する subprocess.run side_effect。"""
    Image.new(mode, (10, 10), "red").save(out_path)


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_invokes_screencapture(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=31, width=1440, height=869)
    out = tmp_path / "page.png"

    def side_effect(cmd, **kwargs):
        _stub_screencapture(out)

    mock_run.side_effect = side_effect

    capture_rect(geom, out)
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "screencapture"
    assert kwargs.get("check") is True


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_correct_R_argument(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=10, y=20, width=300, height=400)
    out = tmp_path / "p.png"
    mock_run.side_effect = lambda cmd, **kw: _stub_screencapture(out)
    capture_rect(geom, out)
    cmd = mock_run.call_args[0][0]
    r_index = cmd.index("-R")
    assert cmd[r_index + 1] == "10,20,300,400"


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_silent_flag(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=0, width=100, height=100)
    out = tmp_path / "p.png"
    mock_run.side_effect = lambda cmd, **kw: _stub_screencapture(out)
    capture_rect(geom, out)
    cmd = mock_run.call_args[0][0]
    assert "-x" in cmd


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_output_path(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=0, width=100, height=100)
    out = tmp_path / "p.png"
    mock_run.side_effect = lambda cmd, **kw: _stub_screencapture(out)
    capture_rect(geom, out)
    cmd = mock_run.call_args[0][0]
    assert str(out) in cmd


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_strips_alpha_channel(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=0, width=10, height=10)
    out = tmp_path / "p.png"
    mock_run.side_effect = lambda cmd, **kw: _stub_screencapture(out, mode="RGBA")
    capture_rect(geom, out)
    assert Image.open(out).mode == "RGB"


def test_flatten_alpha_keeps_rgb_unchanged(tmp_path: Path) -> None:
    p = tmp_path / "rgb.png"
    Image.new("RGB", (5, 5), "blue").save(p)
    mtime = p.stat().st_mtime_ns
    _flatten_alpha(p)
    assert p.stat().st_mtime_ns == mtime  # 早期 return で書き戻しなし
    assert Image.open(p).mode == "RGB"


def test_flatten_alpha_converts_rgba_to_rgb(tmp_path: Path) -> None:
    p = tmp_path / "rgba.png"
    Image.new("RGBA", (5, 5), (255, 0, 0, 128)).save(p)
    _flatten_alpha(p)
    assert Image.open(p).mode == "RGB"
