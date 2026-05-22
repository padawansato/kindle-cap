"""Typer-based CLI entry points for kindle_cap."""

import logging
import re
import sys
from pathlib import Path

import typer

from .config import CaptureConfig, Direction
from .orchestrator import run as orchestrator_run
from .pdf import PdfBuildError, build_pdf
from .preflight import PreflightError

# `page_{n:03d}.png` で生成された PNG を **数値順** に並べるためのキー。
# 書籍が 1000 ページを超えると 3 桁と 4 桁が混在し、辞書順 sort では
# `page_1000.png` が `page_101.png` より先に来てしまうため数値で比較する。
_PAGE_NUM_RE = re.compile(r"page_(\d+)\.png$")
_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def _page_num(p: Path) -> int:
    m = _PAGE_NUM_RE.match(p.name)
    return int(m.group(1)) if m else 0


def _setup_logging(*, verbose: bool, quiet: bool, log_file: Path | None) -> None:
    """`kindle_cap` ロガーに StreamHandler (stderr) と optional FileHandler を attach。

    `logging.basicConfig` は root logger を触るため避け、`kindle_cap` 名前空間
    のみ操作する。既存ハンドラはクリアしてから設定 (同一プロセス内での再呼出に対応)。"""
    if verbose and quiet:
        raise typer.BadParameter(
            "--verbose と --quiet は同時指定できません",
            param_hint="--verbose / --quiet",
        )
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)

    logger = logging.getLogger("kindle_cap")
    logger.setLevel(level)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


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
    pdf_jpeg_quality: int | None = typer.Option(
        None,
        "--pdf-jpeg-quality",
        help=(
            "PDF 埋め込み画像を JPEG quality N (1-100) で再圧縮。"
            "未指定時は lossless PNG 埋め込み (~10x サイズ)。"
            "テキスト書籍は 80 程度推奨"
        ),
    ),
    progress: bool = typer.Option(
        False,
        "--progress/--no-progress",
        help=(
            "--pdf-jpeg-quality 指定時の JPEG 変換ループ進捗を tqdm で stderr に"
            "表示 (1000+ ページ書籍向け、issue #53)"
        ),
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="DEBUG レベルログを有効化（osascript の cmd/stdout/stderr が見える）",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="WARNING 以上のみ出力（進捗ログを抑制）",
    ),
    log_file: Path | None = typer.Option(
        None,
        "--log-file",
        help="指定時はログをファイルにも記録（長時間ジョブの保険）",
    ),
) -> None:
    _setup_logging(verbose=verbose, quiet=quiet, log_file=log_file)
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

    try:
        config = CaptureConfig(
            name=name,
            pages=pages,
            direction=direction,
            wait=wait,
            out=out,
            keep_png=keep_png,
            pdf_jpeg_quality=pdf_jpeg_quality,
            progress=progress,
        )
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e

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
    pdf_jpeg_quality: int | None = typer.Option(
        None,
        "--pdf-jpeg-quality",
        help=(
            "PDF 埋め込み画像を JPEG quality N (1-100) で再圧縮。未指定時は lossless PNG 埋め込み"
        ),
    ),
    progress: bool = typer.Option(
        False,
        "--progress/--no-progress",
        help=(
            "--pdf-jpeg-quality 指定時の JPEG 変換ループ進捗を tqdm で stderr に"
            "表示 (1000+ ページ書籍向け、issue #53)"
        ),
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="DEBUG レベルログを有効化",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="WARNING 以上のみ出力",
    ),
    log_file: Path | None = typer.Option(
        None,
        "--log-file",
        help="指定時はログをファイルにも記録",
    ),
) -> None:
    _setup_logging(verbose=verbose, quiet=quiet, log_file=log_file)
    pngs = sorted(directory.glob("page_*.png"), key=_page_num)
    if not pngs:
        typer.echo(f"[エラー] {directory} に page_*.png が見つかりません", err=True)
        raise typer.Exit(code=1)
    out_path = directory.parent / f"{directory.name}.pdf"
    try:
        build_pdf(pngs, out_path, jpeg_quality=pdf_jpeg_quality, progress=progress)
    except PdfBuildError as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(code=1) from e
    except ValueError as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(f"PDF を作成しました: {out_path}")


def run_capture() -> None:
    typer.run(capture)


def run_rebuild_pdf() -> None:
    typer.run(rebuild_pdf)
