"""Typer-based CLI entry points for kindle_cap."""

from pathlib import Path

import typer

from .config import CaptureConfig, Direction
from .orchestrator import run as orchestrator_run
from .pdf import PdfBuildError, build_pdf
from .preflight import PreflightError


def capture(
    pages: int = typer.Option(..., "--pages", help="撮影ページ数"),
    direction: Direction | None = typer.Option(
        None,
        "--direction",
        help="rtl=右綴じ、ltr=左綴じ（--auto-direction を使う場合は不要）",
        case_sensitive=False,
    ),
    auto_direction: bool = typer.Option(
        False,
        "--auto-direction",
        help="表紙起点で direction を試写判定（rtl/ltr の手動指定が不要）",
    ),
    name: str = typer.Option(
        None,
        "--name",
        help="書籍名（出力ディレクトリ名）。未指定時はプロンプトで聞きます",
    ),
    wait: float = typer.Option(1.0, "--wait", help="ページ送り後の待機秒"),
    out: Path = typer.Option(Path("output"), "--out", help="出力先ディレクトリ"),
    keep_png: bool = typer.Option(
        True,
        "--keep-png/--no-keep-png",
        help="中間 PNG を保持",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="1 枚だけ撮影し PDF は作らない",
    ),
    auto_stop: bool = typer.Option(
        False,
        "--auto-stop",
        help="連続する 2 ページが同一なら書籍末尾と判断して停止",
    ),
) -> None:
    if direction is not None and auto_direction:
        raise typer.BadParameter(
            "--direction と --auto-direction は同時指定できません",
            param_hint="--direction / --auto-direction",
        )
    if direction is None and not auto_direction:
        raise typer.BadParameter(
            "--direction または --auto-direction のいずれかを指定してください",
            param_hint="--direction / --auto-direction",
        )

    if name is None:
        name = typer.prompt("書籍名 (出力ディレクトリ名)")

    config = CaptureConfig(
        name=name,
        pages=pages,
        direction=direction,
        wait=wait,
        out=out,
        keep_png=keep_png,
    )

    try:
        orchestrator_run(
            config,
            dry_run=dry_run,
            auto_stop=auto_stop,
            auto_direction=auto_direction,
        )
    except PreflightError as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(code=1) from e
    except PdfBuildError as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(code=1) from e


def rebuild_pdf(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="page_*.png を含むディレクトリ",
    ),
) -> None:
    pngs = sorted(directory.glob("page_*.png"))
    if not pngs:
        typer.echo(f"[エラー] {directory} に page_*.png が見つかりません", err=True)
        raise typer.Exit(code=1)
    out_path = directory.parent / f"{directory.name}.pdf"
    try:
        build_pdf(pngs, out_path)
    except PdfBuildError as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(f"PDF を作成しました: {out_path}")


def run_capture() -> None:
    typer.run(capture)


def run_rebuild_pdf() -> None:
    typer.run(rebuild_pdf)
