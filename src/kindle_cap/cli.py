"""Typer-based CLI entry points for kindle_cap."""
from pathlib import Path

import typer

from .config import CaptureConfig, Direction
from .orchestrator import run as orchestrator_run
from .orchestrator import run_library as orchestrator_run_library
from .pdf import build_pdf
from .preflight import PreflightError


def capture(
    pages: int = typer.Option(..., "--pages", help="撮影ページ数"),
    direction: Direction = typer.Option(
        ..., "--direction", help="rtl=右綴じ、ltr=左綴じ",
        case_sensitive=False,
    ),
    name: str = typer.Option(
        None, "--name",
        help="書籍名（出力ディレクトリ名）。未指定時はプロンプトで聞きます",
    ),
    wait: float = typer.Option(1.0, "--wait", help="ページ送り後の待機秒"),
    out: Path = typer.Option(Path("output"), "--out", help="出力先ディレクトリ"),
    keep_png: bool = typer.Option(
        True, "--keep-png/--no-keep-png", help="中間 PNG を保持",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="1 枚だけ撮影し PDF は作らない",
    ),
    auto_stop: bool = typer.Option(
        False, "--auto-stop",
        help="連続する 2 ページが同一なら書籍末尾と判断して停止",
    ),
    from_library: bool = typer.Option(
        False, "--from-library",
        help="ライブラリ画面から書籍を順次クリック→撮影→閉じる、を繰り返す",
    ),
    max_books: int = typer.Option(
        10, "--max-books",
        help="--from-library 時の上限冊数",
    ),
    n_cols: int = typer.Option(
        6, "--n-cols",
        help="--from-library 時のグリッド列数（Kindle のウィンドウサイズに依存）",
    ),
    book_open_wait: float = typer.Option(
        2.0, "--book-open-wait",
        help="--from-library 時、本を開いた後の待機秒",
    ),
    library_open_wait: float = typer.Option(
        1.0, "--library-open-wait",
        help="--from-library 時、本を閉じてライブラリに戻った後の待機秒",
    ),
) -> None:
    # library モードでは name は連番固定なのでプロンプトしない
    if not from_library and name is None:
        name = typer.prompt("書籍名 (出力ディレクトリ名)")

    # library モードでは name はダミー（_capture_book 内で連番に置き換わる）
    config = CaptureConfig(
        name=(name or "library-loop"),
        pages=pages,
        direction=direction,
        wait=wait,
        out=out,
        keep_png=keep_png,
    )

    try:
        if from_library:
            orchestrator_run_library(
                config,
                max_books=max_books,
                n_cols=n_cols,
                book_open_wait=book_open_wait,
                library_open_wait=library_open_wait,
            )
        else:
            orchestrator_run(config, dry_run=dry_run, auto_stop=auto_stop)
    except PreflightError as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(code=1)


def rebuild_pdf(
    directory: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="page_*.png を含むディレクトリ",
    ),
) -> None:
    pngs = sorted(directory.glob("page_*.png"))
    if not pngs:
        typer.echo(f"[エラー] {directory} に page_*.png が見つかりません", err=True)
        raise typer.Exit(code=1)
    out_path = directory.parent / f"{directory.name}.pdf"
    build_pdf(pngs, out_path)
    typer.echo(f"PDF を作成しました: {out_path}")


def run_capture() -> None:
    typer.run(capture)


def run_rebuild_pdf() -> None:
    typer.run(rebuild_pdf)
