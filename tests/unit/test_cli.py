from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from kindle_cap.cli import capture, rebuild_pdf
from kindle_cap.config import Direction
from kindle_cap.pdf import PdfBuildError

runner = CliRunner()


def _make_app(func: Callable[..., None]) -> typer.Typer:
    app = typer.Typer()
    app.command()(func)
    return app


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_with_all_flags(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "test-book",
            "--pages",
            "3",
            "--direction",
            "rtl",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    config_arg = mock_run.call_args.args[0]
    assert config_arg.name == "test-book"
    assert config_arg.pages == 3
    assert config_arg.direction.value == "rtl"
    assert config_arg.out == tmp_path
    assert config_arg.wait == 1.0
    assert config_arg.keep_png is True


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_prompts_when_name_missing(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--pages",
            "3",
            "--direction",
            "rtl",
            "--out",
            str(tmp_path),
        ],
        input="prompted-name\n",
    )
    assert result.exit_code == 0, result.output
    config_arg = mock_run.call_args.args[0]
    assert config_arg.name == "prompted-name"


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_dry_run_passed_through(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "1",
            "--direction",
            "ltr",
            "--out",
            str(tmp_path),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs.get("dry_run") is True


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_auto_stop_passed_through(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "100",
            "--direction",
            "rtl",
            "--out",
            str(tmp_path),
            "--auto-stop",
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs.get("auto_stop") is True


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_auto_stop_default_false(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "5",
            "--direction",
            "rtl",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs.get("auto_stop") is False


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_no_keep_png(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "1",
            "--direction",
            "ltr",
            "--out",
            str(tmp_path),
            "--no-keep-png",
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.args[0].keep_png is False


@patch("kindle_cap.cli.build_pdf")
def test_rebuild_pdf_writes_to_parent_with_dir_name(
    mock_build: MagicMock,
    tmp_path: Path,
) -> None:
    book = tmp_path / "my-book"
    book.mkdir()
    (book / "page_001.png").write_bytes(b"a")
    (book / "page_002.png").write_bytes(b"b")

    app = _make_app(rebuild_pdf)
    result = runner.invoke(app, [str(book)])

    assert result.exit_code == 0, result.output
    pngs_arg, out_arg = mock_build.call_args.args
    assert out_arg == tmp_path / "my-book.pdf"
    assert [p.name for p in pngs_arg] == ["page_001.png", "page_002.png"]


def test_rebuild_pdf_missing_dir_exits_nonzero(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    app = _make_app(rebuild_pdf)
    result = runner.invoke(app, [str(missing)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# PdfBuildError (ディスク容量不足) のハンドリング
# ---------------------------------------------------------------------------


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_pdf_build_error_exits_nonzero_with_message(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    """PDF 生成が ENOSPC で失敗したら exit 1 + 説明的メッセージを stderr に出す."""
    mock_run.side_effect = PdfBuildError("ディスク容量不足で PDF を作成できませんでした。")
    app = _make_app(capture)
    result = runner.invoke(
        app,
        ["--name", "x", "--pages", "1", "--direction", "rtl", "--out", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "ディスク容量不足" in result.output


@patch("kindle_cap.cli.build_pdf")
def test_rebuild_pdf_build_error_exits_nonzero_with_message(
    mock_build: MagicMock, tmp_path: Path
) -> None:
    """rebuild_pdf でも ENOSPC は exit 1 + 説明的メッセージ."""
    mock_build.side_effect = PdfBuildError("ディスク容量不足で PDF を作成できませんでした。")
    book = tmp_path / "my-book"
    book.mkdir()
    (book / "page_001.png").write_bytes(b"a")

    app = _make_app(rebuild_pdf)
    result = runner.invoke(app, [str(book)])

    assert result.exit_code != 0
    assert "ディスク容量不足" in result.output


# ---------------------------------------------------------------------------
# --auto-direction フラグと排他バリデーション
# ---------------------------------------------------------------------------


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_auto_direction_routes_to_run_with_flag(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """--auto-direction 単体指定で auto_direction=True、direction は None"""
    app = _make_app(capture)
    result = runner.invoke(
        app,
        ["--name", "x", "--pages", "5", "--auto-direction", "--out", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs.get("auto_direction") is True
    assert mock_run.call_args.args[0].direction is None


def test_capture_direction_and_auto_direction_conflict_exits_nonzero(
    tmp_path: Path,
) -> None:
    """--direction と --auto-direction の同時指定はエラー"""
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "5",
            "--direction",
            "rtl",
            "--auto-direction",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "同時指定" in result.output


def test_capture_neither_direction_nor_auto_direction_exits_nonzero(
    tmp_path: Path,
) -> None:
    """--direction も --auto-direction も未指定はエラー"""
    app = _make_app(capture)
    result = runner.invoke(
        app,
        ["--name", "x", "--pages", "5", "--out", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "いずれか" in result.output


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_existing_direction_still_works(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """後方互換: --direction rtl 単体で従来通り動く"""
    app = _make_app(capture)
    result = runner.invoke(
        app,
        ["--name", "x", "--pages", "5", "--direction", "rtl", "--out", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.args[0].direction is Direction.RTL
    assert mock_run.call_args.kwargs.get("auto_direction") is False


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_auto_direction_combined_with_auto_stop(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """--auto-direction と --auto-stop を組み合わせて指定できる"""
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "100",
            "--auto-direction",
            "--auto-stop",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs.get("auto_direction") is True
    assert mock_run.call_args.kwargs.get("auto_stop") is True


# ---------------------------------------------------------------------------
# --pdf-jpeg-quality
# ---------------------------------------------------------------------------


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_pdf_jpeg_quality_default_is_none(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        ["--name", "x", "--pages", "1", "--direction", "rtl", "--out", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.args[0].pdf_jpeg_quality is None


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_pdf_jpeg_quality_passes_through(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "1",
            "--direction",
            "rtl",
            "--out",
            str(tmp_path),
            "--pdf-jpeg-quality",
            "80",
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.args[0].pdf_jpeg_quality == 80


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_pdf_jpeg_quality_out_of_range_exits_nonzero(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    """範囲外 (0 / 101) は CaptureConfig の validation で BadParameter になり exit 非 0."""
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name",
            "x",
            "--pages",
            "1",
            "--direction",
            "rtl",
            "--out",
            str(tmp_path),
            "--pdf-jpeg-quality",
            "0",
        ],
    )
    assert result.exit_code != 0
    assert not mock_run.called


@patch("kindle_cap.cli.build_pdf")
def test_rebuild_pdf_pdf_jpeg_quality_passes_through(mock_build: MagicMock, tmp_path: Path) -> None:
    book = tmp_path / "my-book"
    book.mkdir()
    (book / "page_001.png").write_bytes(b"a")
    app = _make_app(rebuild_pdf)
    result = runner.invoke(app, [str(book), "--pdf-jpeg-quality", "70"])
    assert result.exit_code == 0, result.output
    assert mock_build.call_args.kwargs.get("jpeg_quality") == 70


@patch("kindle_cap.cli.build_pdf")
def test_rebuild_pdf_pdf_jpeg_quality_default_is_none(
    mock_build: MagicMock, tmp_path: Path
) -> None:
    book = tmp_path / "my-book"
    book.mkdir()
    (book / "page_001.png").write_bytes(b"a")
    app = _make_app(rebuild_pdf)
    result = runner.invoke(app, [str(book)])
    assert result.exit_code == 0, result.output
    assert mock_build.call_args.kwargs.get("jpeg_quality") is None
