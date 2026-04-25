from pathlib import Path
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from kindle_cap.cli import capture, rebuild_pdf

runner = CliRunner()


def _make_app(func) -> typer.Typer:
    app = typer.Typer()
    app.command()(func)
    return app


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_with_all_flags(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name", "test-book",
            "--pages", "3",
            "--direction", "rtl",
            "--out", str(tmp_path),
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
            "--pages", "3",
            "--direction", "rtl",
            "--out", str(tmp_path),
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
            "--name", "x",
            "--pages", "1",
            "--direction", "ltr",
            "--out", str(tmp_path),
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
            "--name", "x",
            "--pages", "100",
            "--direction", "rtl",
            "--out", str(tmp_path),
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
            "--name", "x",
            "--pages", "5",
            "--direction", "rtl",
            "--out", str(tmp_path),
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
            "--name", "x",
            "--pages", "1",
            "--direction", "ltr",
            "--out", str(tmp_path),
            "--no-keep-png",
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.args[0].keep_png is False


@patch("kindle_cap.cli.build_pdf")
def test_rebuild_pdf_writes_to_parent_with_dir_name(
    mock_build: MagicMock, tmp_path: Path,
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
