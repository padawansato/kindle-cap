"""Typer-based CLI entry points for kindle_cap."""

import hashlib
import logging
import re
import sys
import tempfile
from pathlib import Path
from time import sleep

import typer

from .batch import run_all, select_books
from .capture import capture_rect
from .config import CaptureConfig, Direction
from .keys import KeystrokeError
from .orchestrator import run as orchestrator_run
from .pdf import PdfBuildError, build_pdf
from .preflight import PreflightError
from .window import KindleActivationError, WindowGeometryError

logger = logging.getLogger(__name__)

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
    crop_top: int = typer.Option(
        0,
        "--crop-top",
        help=(
            "撮影矩形の上端から削る量 (論理ポイント)。System Events のウィンドウ frame は"
            "タイトルバー (信号機ボタン) を含むため、固定型書籍で写り込む場合に指定。"
            "まず --dry-run で値を確認 (issue #69)"
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
            crop_top=crop_top,
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
    except (
        PreflightError,
        PdfBuildError,
        WindowGeometryError,
        KindleActivationError,
        KeystrokeError,
        ValueError,  # crop_top >= ウィンドウ高さ など、実機で初めて分かる設定不整合 (issue #69)
    ) as e:
        logger.error("%s", e)
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
    except (PdfBuildError, ValueError) as e:
        logger.error("%s", e)
        raise typer.Exit(code=1) from e
    logger.info("PDF を作成しました: %s", out_path)


def capture_all(
    out: Path = typer.Option(Path("output"), "--out", help="出力先ディレクトリ"),
    wait: float = typer.Option(1.0, "--wait", help="ページ送り後の待機秒"),
    list_only: bool = typer.Option(
        False, "--list", help="ライブラリの書籍を列挙して終了 (撮影しない)"
    ),
    only: str | None = typer.Option(None, "--only", help="タイトルの部分一致で対象を絞る"),
    limit: int | None = typer.Option(
        None, "--limit", help="撮影する冊数の上限 (スキップは数えない)"
    ),
    include_pdf: bool = typer.Option(
        False, "--include-pdf", help="Send to Kindle した PDF も撮影する (既定は飛ばす)"
    ),
    max_pages: int = typer.Option(
        3000, "--max-pages", help="1 冊あたりの撮影上限。末尾は同一ページ連続で自動検出する"
    ),
    pdf_jpeg_quality: int | None = typer.Option(
        None,
        "--pdf-jpeg-quality",
        help="PDF 埋め込み画像を JPEG quality N (1-100) で再圧縮。テキスト書籍は 80 程度推奨",
    ),
    progress: bool = typer.Option(
        False, "--progress/--no-progress", help="JPEG 変換ループの進捗を表示"
    ),
    crop_top: int = typer.Option(
        0, "--crop-top", help="撮影矩形の上端から削る量 (論理ポイント、issue #69)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="DEBUG レベルログを有効化"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="WARNING 以上のみ出力"),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="指定時はログをファイルにも記録（長時間ジョブの保険）"
    ),
) -> None:
    """Kindle.app のライブラリにある書籍を順に開き、先頭に戻して全ページ撮影 → PDF にする.

    本を手で選んで 1 ページ目を開く準備は不要。既に `<out>/<書籍名>.pdf` がある本は
    飛ばすので、中断しても再実行で続きから進む。撮影した本の読書位置は末尾に移る。
    サンプル本は書籍情報シートが割り込むなど挙動が違うので対象外。
    """
    _setup_logging(verbose=verbose, quiet=quiet, log_file=log_file)
    # PyObjC (アクセシビリティ API) はこのコマンドでしか使わないので遅延 import
    from . import ax, library
    from .reader import parse_status, rewind_to_start
    from .window import get_window_geometry

    try:
        app = ax.app_element()
    except ax.KindleAXError as e:
        logger.error("%s", e)
        raise typer.Exit(code=1) from e
    ax.activate()
    sleep(0.5)

    def geometry() -> tuple[int, int, int, int]:
        g = get_window_geometry()
        return (g.x, g.y, g.width, g.height)

    if library.in_reader(app):
        logger.info("リーダーが開いているのでライブラリに戻します")
        library.close_book(app, geometry=geometry())

    books = library.list_books(app)
    if list_only:
        for book, name, reason in select_books(books, out=out, include_pdf=include_pdf, only=only):
            state = (
                f"{book.progress_pct}%"
                if book.progress_pct is not None
                else ("DL済" if book.downloaded else "未DL")
            )
            mark = f"  → skip ({reason})" if reason else ""
            typer.echo(f"{state:>4} | {book.title} | {book.author} | {' '.join(book.tags)}{mark}")
            if name != book.title:
                typer.echo(f"       出力名: {name}")
        typer.echo(f"{len(books)} 冊")
        return

    def read_status() -> tuple[int, int] | None:
        g = geometry()
        library.dismiss_sheet(app)
        text: str | None = None
        for _ in range(3):
            ax.sweep_mouse(*g)
            found = ax.find(app, "AXStaticText", lambda d: parse_status(d) is not None)
            if found:
                text = ax.description(found[0])
                break
        ax.press_escape()
        ax.park_mouse(*g)
        sleep(0.4)
        return parse_status(text)

    def page_hash() -> str:
        library.dismiss_sheet(app)
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "probe.png"
            capture_rect(get_window_geometry(), png)
            return hashlib.md5(png.read_bytes()).hexdigest()

    def capture_book(book: library.Book, name: str) -> None:
        ax.activate()
        library.dismiss_sheet(app)
        direction = rewind_to_start(
            press=ax.key_code,
            page_hash=page_hash,
            read_status=read_status,
            sleeper=sleep,
            wait=max(0.4, wait * 0.5),
        )
        logger.info("先頭に戻しました (direction=%s)", direction.value)
        library.dismiss_sheet(app)
        ax.park_mouse(*geometry())
        config = CaptureConfig(
            name=name,
            pages=max_pages,
            direction=direction,
            wait=wait,
            out=out,
            keep_png=True,
            pdf_jpeg_quality=pdf_jpeg_quality,
            progress=progress,
            crop_top=crop_top,
        )

        def before_capture() -> None:
            # サンプル末尾などで被さるシートを閉じる。閉じた直後は chrome が出るので隠す
            if library.dismiss_sheet(app):
                ax.press_escape()
                ax.park_mouse(*geometry())
                sleep(0.5)

        orchestrator_run(config, auto_stop=True, before_capture=before_capture)
        n_pages = len(list((out / name).glob("page_*.png")))
        if n_pages < 2:
            (out / f"{name}.pdf").unlink(missing_ok=True)
            raise RuntimeError(
                f"{n_pages} ページしか撮れていません (ページ送りが効いていない可能性)。PDF は削除しました"
            )

    results = run_all(
        books,
        out=out,
        include_pdf=include_pdf,
        only=only,
        limit=limit,
        open_book=lambda b: library.open_book(app, b),
        close_book=lambda: library.close_book(app, geometry=geometry()),
        capture_book=capture_book,
    )
    captured = [r for r in results if r.status == "captured"]
    failed = [r for r in results if r.status == "failed"]
    skipped = [r for r in results if r.status == "skipped"]
    logger.info("完了: 撮影 %d / スキップ %d / 失敗 %d", len(captured), len(skipped), len(failed))
    for r in failed:
        logger.error("失敗: %s: %s", r.book.title, r.error)
    if failed:
        raise typer.Exit(code=1)


def run_capture() -> None:
    typer.run(capture)


def run_capture_all() -> None:
    typer.run(capture_all)


def run_rebuild_pdf() -> None:
    typer.run(rebuild_pdf)
