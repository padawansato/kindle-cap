import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from kindle_cap.capture import (
    CaptureError,
    _build_screencapture_args,
    _flatten_alpha,
    capture_rect,
)
from kindle_cap.config import Geometry

# ---------------------------------------------------------------------------
# 純粋関数 _build_screencapture_args: screencapture コマンド引数を組み立てる
# ---------------------------------------------------------------------------


def test_build_args_starts_with_screencapture(tmp_path: Path) -> None:
    args = _build_screencapture_args(Geometry(0, 0, 100, 100), tmp_path / "p.png")
    assert args[0] == "screencapture"


def test_build_args_includes_R_with_csv_geometry(tmp_path: Path) -> None:
    args = _build_screencapture_args(Geometry(10, 20, 300, 400), tmp_path / "p.png")
    r_idx = args.index("-R")
    assert args[r_idx + 1] == "10,20,300,400"


def test_build_args_includes_silent_flag(tmp_path: Path) -> None:
    args = _build_screencapture_args(Geometry(0, 0, 100, 100), tmp_path / "p.png")
    assert "-x" in args


def test_build_args_includes_output_path_as_string(tmp_path: Path) -> None:
    out = tmp_path / "page_001.png"
    args = _build_screencapture_args(Geometry(0, 0, 100, 100), out)
    assert str(out) in args


def test_build_args_handles_zero_origin(tmp_path: Path) -> None:
    args = _build_screencapture_args(Geometry(0, 0, 100, 100), tmp_path / "p.png")
    assert args[args.index("-R") + 1] == "0,0,100,100"


def test_build_args_handles_negative_origin(tmp_path: Path) -> None:
    args = _build_screencapture_args(Geometry(-50, -10, 100, 100), tmp_path / "p.png")
    assert args[args.index("-R") + 1] == "-50,-10,100,100"


@pytest.mark.parametrize(
    "x,y,w,h,expected",
    [
        # 左の外部モニタ (1920x1080) がメインの左に配置
        (-1920, 0, 1920, 1080, "-1920,0,1920,1080"),
        # 右の外部モニタ
        (1440, 0, 1920, 1080, "1440,0,1920,1080"),
        # 上の外部モニタ
        (0, -1080, 1920, 1080, "0,-1080,1920,1080"),
        # 右上の遠い 4K
        (3840, -1080, 3840, 2160, "3840,-1080,3840,2160"),
        # メイン直上のサブモニタ
        (200, -800, 1024, 768, "200,-800,1024,768"),
    ],
)
def test_build_args_supports_multi_display_origins(
    tmp_path: Path,
    x: int,
    y: int,
    w: int,
    h: int,
    expected: str,
) -> None:
    """マルチディスプレイ環境では Kindle が任意の仮想スクリーン座標にいる可能性。
    外部ディスプレイの座標 (負値・大値) でも screencapture 引数を正しく組み立てる。
    """
    args = _build_screencapture_args(Geometry(x, y, w, h), tmp_path / "p.png")
    assert args[args.index("-R") + 1] == expected


def test_build_args_handles_path_with_spaces(tmp_path: Path) -> None:
    out = tmp_path / "name with space.png"
    args = _build_screencapture_args(Geometry(0, 0, 100, 100), out)
    # subprocess は list 形式で渡すのでクオート不要、そのまま str(path) が入っていればよい
    assert str(out) in args


def test_build_args_handles_japanese_filename(tmp_path: Path) -> None:
    out = tmp_path / "ページ_001.png"
    args = _build_screencapture_args(Geometry(0, 0, 100, 100), out)
    assert str(out) in args


# ---------------------------------------------------------------------------
# 純粋関数 _flatten_alpha: PNG の alpha channel を除去
# ---------------------------------------------------------------------------


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


def test_flatten_alpha_converts_la_to_rgb(tmp_path: Path) -> None:
    """L+alpha (グレースケール+透明度) も RGB に変換されること"""
    p = tmp_path / "la.png"
    Image.new("LA", (5, 5), (128, 128)).save(p)
    _flatten_alpha(p)
    assert Image.open(p).mode == "RGB"


def test_flatten_alpha_converts_palette_to_rgb(tmp_path: Path) -> None:
    """パレット (P) モードも RGB に変換されること"""
    p = tmp_path / "p.png"
    Image.new("P", (5, 5)).save(p)
    _flatten_alpha(p)
    assert Image.open(p).mode == "RGB"


def test_flatten_alpha_preserves_dimensions(tmp_path: Path) -> None:
    p = tmp_path / "rgba.png"
    Image.new("RGBA", (123, 456), (0, 0, 0, 0)).save(p)
    _flatten_alpha(p)
    img = Image.open(p)
    assert img.size == (123, 456)


def test_flatten_alpha_replaces_transparent_with_white_background(tmp_path: Path) -> None:
    p = tmp_path / "rgba.png"
    # 完全透明の RGBA は flatten 後に白くなる
    Image.new("RGBA", (5, 5), (0, 0, 0, 0)).save(p)
    _flatten_alpha(p)
    img = Image.open(p)
    assert img.getpixel((0, 0)) == (255, 255, 255)


# ---------------------------------------------------------------------------
# 薄いラッパー capture_rect: subprocess 呼び出し + flatten の連携
# ---------------------------------------------------------------------------


def _stub_screencapture_factory(out_path: Path, mode: str = "RGBA") -> Callable[..., None]:
    def side_effect(cmd: list[str], **kwargs: Any) -> None:
        Image.new(mode, (10, 10), "red" if mode == "RGB" else (255, 0, 0, 200)).save(out_path)

    return side_effect


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_writes_rgb_png_after_flatten(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    out = tmp_path / "p.png"
    mock_run.side_effect = _stub_screencapture_factory(out, mode="RGBA")
    capture_rect(Geometry(0, 0, 10, 10), out)
    assert Image.open(out).mode == "RGB"


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_built_args_to_subprocess(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    out = tmp_path / "p.png"
    mock_run.side_effect = _stub_screencapture_factory(out)
    capture_rect(Geometry(10, 20, 30, 40), out)
    args = mock_run.call_args[0][0]
    expected = _build_screencapture_args(Geometry(10, 20, 30, 40), out)
    assert args == expected


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_uses_check_true(mock_run: MagicMock, tmp_path: Path) -> None:
    out = tmp_path / "p.png"
    mock_run.side_effect = _stub_screencapture_factory(out)
    capture_rect(Geometry(0, 0, 10, 10), out)
    assert mock_run.call_args.kwargs.get("check") is True


# ---------------------------------------------------------------------------
# 防御層: macOS の screencapture は書き込み失敗時でも exit 0 で抜けることがある。
# check=True だけでは検知できないので out_path の存在を確認し、無ければ
# CaptureError を上げて呼び出し元に意味のあるエラーを返す。
# ---------------------------------------------------------------------------


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_raises_capture_error_when_file_not_created(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    out = tmp_path / "missing.png"
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr="screencapture: cannot write file"
    )
    with pytest.raises(CaptureError):
        capture_rect(Geometry(0, 0, 10, 10), out)


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_error_includes_stderr_text(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    out = tmp_path / "missing.png"
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="",
        stderr="cannot write file to intended destination",
    )
    with pytest.raises(CaptureError, match="cannot write file to intended destination"):
        capture_rect(Geometry(0, 0, 10, 10), out)


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_error_includes_out_path(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    out = tmp_path / "page_153.png"
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with pytest.raises(CaptureError, match=r"page_153\.png"):
        capture_rect(Geometry(0, 0, 10, 10), out)
