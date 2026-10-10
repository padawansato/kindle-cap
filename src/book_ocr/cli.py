"""book-ocr CLI entry point."""

from __future__ import annotations

import re
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import typer

from book_ocr import orchestrator, writer
from book_ocr.engines.yomitoku import YomiTokuEngine
from book_ocr.exporters.book_md import render_book_md
from book_ocr.exporters.json_index import render_index
from book_ocr.exporters.searchable_pdf import (
    SearchablePdfError,
    build_image_pdf,
    overlay_text_layer,
)
from book_ocr.models import BookMetadata, PageText
from book_ocr.preflight import PreflightError, check_disk_space
from book_ocr.protocols import OCREngine

# render_page_md と対称な逆解析: 先頭の "<!-- page:NNN -->\n\n" を取り除く
_PAGE_MARKER_RE = re.compile(r"^<!--\s*page:\d+\s*-->\s*\n+", re.DOTALL)


def run_ocr_pipeline(
    book_dir: Path,
    name: str | None = None,
    device: str = "mps",
    reading_order: str = "auto",
    ignore_meta: bool = True,
    out: Path | None = None,
    engine: OCREngine | None = None,
    chunk_size: int | None = None,
    timeout_sec: float = 1800.0,
    start_page: int = 1,
    end_page: int | None = None,
    progress: bool = True,
    skip_existing: bool = False,
    ignore_disk_check: bool = False,
    figure: bool = True,
    searchable_pdf: bool = False,
    source_pdf: Path | None = None,
) -> Path:
    """指定した book_dir 内の page_*.png を OCR して Markdown / index.json を出力する.

    `searchable_pdf=True` なら OCR の生 JSON から `<out_dir>/<title>.searchable.pdf` も
    作る (issue #70)。元画像は `source_pdf` (省略時は kindle-cap が書いた
    `<book_dir の親>/<book_dir 名>.pdf`)。無ければ book_dir の全 PNG から組む。

    `engine=None` のときは `YomiTokuEngine` を生成する。テストでは FakeEngine 等を渡す。

    `start_page` / `end_page` (1-indexed inclusive) で対象範囲を絞れる (issue #39)。
    ファイル名 `page_NNN.png` の NNN 部分でフィルタする。

    Returns:
        生成された book Markdown ファイルのパス。
    """
    if start_page < 1:
        raise ValueError(f"start_page must be >= 1, got {start_page}")
    if end_page is not None and end_page < start_page:
        raise ValueError(f"end_page ({end_page}) must be >= start_page ({start_page})")

    all_pngs = sorted(book_dir.glob("page_*.png"))
    pngs = [p for p in all_pngs if start_page <= _parse_page_number(p) <= (end_page or 10**9)]
    if not pngs:
        raise FileNotFoundError(
            f"No page_*.png in {book_dir} for range "
            f"[{start_page}, {end_page if end_page is not None else 'end'}]"
        )

    title = name or book_dir.name
    out_dir = out or book_dir
    pdf_out = out_dir / f"{title}.searchable.pdf"
    pdf_src = source_pdf or book_dir.parent / f"{book_dir.name}.pdf"

    if not ignore_disk_check:
        extra = 0
        if searchable_pdf:
            # 元 PDF のコピー + テキスト層 (元 PDF が無ければ PNG を全部載せる)
            extra = (
                pdf_src.stat().st_size
                if pdf_src.exists()
                else sum(p.stat().st_size for p in all_pngs)
            )
        check_disk_space(pngs=pngs, out_dir=out_dir, chunk_size=chunk_size, extra_bytes=extra)

    engine = engine or YomiTokuEngine(
        device=device,
        reading_order=reading_order,
        ignore_meta=ignore_meta,
        chunk_size=chunk_size,
        timeout_sec=timeout_sec,
        progress=progress,
        figure=figure,
        figure_out_dir=(out_dir / "figures") if figure else None,
        # OCR の生 JSON は md と並べて pages/ に置く (issue #70)。searchable PDF は
        # ここから作るので、再 OCR なしで PDF だけ作り直せる。
        json_out_dir=out_dir / "pages",
    )
    captured_at = datetime.now(UTC)

    existing_pages: list[PageText] = []
    pngs_to_ocr: list[Path] = list(pngs)
    if skip_existing:
        existing_pages, pngs_to_ocr = _partition_existing_pages(
            pngs, out_dir / "pages", engine.name
        )

    initial_meta = BookMetadata(
        title=title,
        page_count=len(pngs),
        captured_at=captured_at,
        ocr_engine=engine.name,
        output_dir=out_dir,
        ocr_engine_version=engine.version,
        ocr_settings=engine.settings,
    )

    t0 = time.perf_counter()
    if pngs_to_ocr:
        if existing_pages:
            new_pages = engine.run_batch(pngs_to_ocr)
            pages = _merge_pages(existing_pages, new_pages)
            book_md_str = render_book_md(pages)
        else:
            pages, _index_dict_pre, book_md_str = orchestrator.run(
                engine, initial_meta, pngs_to_ocr
            )
    else:
        # 全ページ既存 → engine 呼ばず、保存済み内容で book_md を再生成
        pages = sorted(existing_pages, key=lambda p: p.page_number)
        book_md_str = render_book_md(pages)
    duration_sec = time.perf_counter() - t0
    finished_at = datetime.now(UTC)

    if searchable_pdf:
        _build_searchable_pdf(pages, all_pngs, pdf_src, pdf_out)
        initial_meta = replace(initial_meta, searchable_pdf=pdf_out.name)

    meta = replace(
        initial_meta,
        ocr_runtime={
            "started_at": captured_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_sec": round(duration_sec, 3),
        },
    )
    index_dict = render_index(meta, pages)
    writer.write_outputs(
        out_dir=out_dir,
        book_md_filename=f"{title}.md",
        index=index_dict,
        book_md=book_md_str,
        pages=pages,
    )
    return out_dir / f"{title}.md"


def ocr(
    book_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="kindle-cap が出力した output/<book>/ ディレクトリ (page_*.png を含む)",
    ),
    name: str | None = typer.Option(None, "--name", help="書籍名 (省略時は book_dir の basename)"),
    device: str = typer.Option("mps", "--device", help="OCR デバイス (mps/cpu/cuda)"),
    reading_order: str = typer.Option(
        "auto",
        "--reading-order",
        help="読み順 (auto/left2right/top2bottom/right2left)",
    ),
    ignore_meta: bool = typer.Option(
        True,
        "--ignore-meta/--no-ignore-meta",
        help="ヘッダー/フッター (Kindle メタ) を除外する",
    ),
    out: Path | None = typer.Option(
        None, "--out", help="出力先ディレクトリ (省略時は book_dir に書き戻す)"
    ),
    chunk_size: int | None = typer.Option(
        None,
        "--chunk-size",
        help=(
            "ページを N 枚ずつ分割して OCR (issue #36)。"
            "巨大本で timeout 回避と線形スケール改善。省略時は全 PNG を 1 subprocess。"
        ),
    ),
    timeout_sec: float = typer.Option(
        1800.0,
        "--timeout-sec",
        help=(
            "yomitoku subprocess 1 回の timeout (秒、issue #37)。"
            "chunked 実行時は 1 chunk あたりの上限。巨大本では延長を検討。"
        ),
    ),
    start_page: int = typer.Option(
        1,
        "--start-page",
        help="OCR 開始ページ番号 (1-indexed inclusive、issue #39)。",
    ),
    end_page: int | None = typer.Option(
        None,
        "--end-page",
        help="OCR 終了ページ番号 (1-indexed inclusive、省略時は最後まで、issue #39)。",
    ),
    progress: bool = typer.Option(
        True,
        "--progress/--no-progress",
        help=(
            "chunked 実行時に tqdm で chunk 単位の進捗を stderr に表示する (issue #38)。"
            "非 tty 環境では自動的に無効化される。"
        ),
    ),
    skip_existing: bool = typer.Option(
        False,
        "--skip-existing",
        help=(
            "既存 `pages/page_NNN.md` があるページの OCR をスキップ (issue #41)。"
            "失敗後の再走で chunk 単位 retry を高速化する。空ファイルは missing 扱い。"
        ),
    ),
    ignore_disk_check: bool = typer.Option(
        False,
        "--ignore-disk-check",
        help=(
            "起動時のディスク容量 preflight をバイパスする (issue #48)。"
            "デフォルトでは入力 PNG × 1.5 のマージンで out_dir / tempdir の残量を確認する。"
        ),
    ),
    figure: bool = typer.Option(
        True,
        "--figure/--no-figure",
        help=(
            "図表領域を切り出して figures/ に保存し、md に参照を埋め込む (EPUB 用)。"
            "図中テキストも --figure_letter で本文に含める。"
        ),
    ),
    searchable_pdf: bool = typer.Option(
        False,
        "--searchable-pdf",
        help=(
            "OCR 結果から文字をコピー・検索できる PDF `<title>.searchable.pdf` を作る (issue #70)。"
            "kindle-cap の `<book>.pdf` に不可視テキスト層を重ねる。"
            "--skip-existing と併用すれば再 OCR なしで PDF だけ作り直せる。"
        ),
    ),
    source_pdf: Path | None = typer.Option(
        None,
        "--source-pdf",
        help="--searchable-pdf の元になる画像 PDF (省略時は `<book_dir の親>/<book_dir 名>.pdf`)。",
    ),
) -> None:
    """指定した book_dir 内の page_*.png を OCR して Markdown / index.json を生成する."""
    try:
        out_path = run_ocr_pipeline(
            book_dir=book_dir,
            name=name,
            device=device,
            reading_order=reading_order,
            ignore_meta=ignore_meta,
            out=out,
            chunk_size=chunk_size,
            timeout_sec=timeout_sec,
            start_page=start_page,
            end_page=end_page,
            progress=progress,
            skip_existing=skip_existing,
            ignore_disk_check=ignore_disk_check,
            figure=figure,
            searchable_pdf=searchable_pdf,
            source_pdf=source_pdf,
        )
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    except (PreflightError, SearchablePdfError) as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"OCR complete: {out_path}")
    if searchable_pdf:
        typer.echo(f"searchable PDF: {out_path.with_name(out_path.stem + '.searchable.pdf')}")


def _parse_page_number(p: Path) -> int:
    """`page_NNN.png` から NNN を取り出す。issue #39 の範囲フィルタで使う。"""
    return int(p.stem.split("_")[-1])


def _partition_existing_pages(
    pngs: list[Path], pages_dir: Path, engine_name: str
) -> tuple[list[PageText], list[Path]]:
    """`--skip-existing` 用 (issue #41): 既存 `pages/page_NNN.md` を読み出して
    PageText に再構成し、未存在のページを OCR 対象として返す。

    既存 md 先頭の `<!-- page:NNN -->` プレフィクスは render_page_md と対称に剥がす。
    空ファイルは `missing` 扱いで再 OCR にまわす (壊れた状態のフォールバック)。"""
    existing: list[PageText] = []
    to_ocr: list[Path] = []
    for png in pngs:
        n = _parse_page_number(png)
        md_path = pages_dir / f"page_{n:03d}.md"
        if not md_path.exists() or md_path.stat().st_size == 0:
            to_ocr.append(png)
            continue
        content = md_path.read_text(encoding="utf-8")
        body = _PAGE_MARKER_RE.sub("", content, count=1)
        body = body.replace('src="../figures/', 'src="figures/')
        # 生 JSON があれば searchable PDF に使えるので引き継ぐ (issue #70)
        json_path = pages_dir / f"page_{n:03d}.json"
        existing.append(
            PageText(
                page_number=n,
                png_path=png,
                markdown=body,
                ocr_engine=engine_name,
                json_path=json_path if json_path.exists() else None,
            )
        )
    return existing, to_ocr


def _build_searchable_pdf(
    pages: list[PageText], all_pngs: list[Path], pdf_src: Path, pdf_out: Path
) -> None:
    """OCR JSON を持つページだけに不可視テキスト層を重ねる (issue #70).

    JSON の無いページ (PR #71 より前に OCR した既存ページなど) は無言で再 OCR せず、
    ページ番号を列挙して警告する。元 PDF が無ければ book_dir の全 PNG から組む。"""
    missing = [p.page_number for p in pages if p.json_path is None]
    if missing:
        typer.echo(
            f"[警告] OCR JSON が無いのでテキスト層を付けられないページ: {missing}"
            " (再 OCR すると付きます)",
            err=True,
        )
    page_jsons = {
        p.page_number: (p.json_path, p.png_path) for p in pages if p.json_path is not None
    }
    if pdf_src.exists():
        overlay_text_layer(pdf_src, pdf_out, page_jsons)
        return
    typer.echo(f"[情報] {pdf_src} が無いので PNG から画像 PDF を組みます", err=True)
    tmp = pdf_out.with_name(pdf_out.name + ".tmp")
    try:
        build_image_pdf(all_pngs, tmp)
        overlay_text_layer(tmp, pdf_out, page_jsons)
    finally:
        tmp.unlink(missing_ok=True)


def _merge_pages(existing: list[PageText], new: list[PageText]) -> list[PageText]:
    """既存ページと新規 OCR ページを page_number 昇順でマージ。重複検出。"""
    combined = sorted(existing + new, key=lambda p: p.page_number)
    seen: set[int] = set()
    for p in combined:
        if p.page_number in seen:
            raise ValueError(f"duplicate page_number {p.page_number} after merge")
        seen.add(p.page_number)
    return combined


def run_ocr() -> None:
    typer.run(ocr)
