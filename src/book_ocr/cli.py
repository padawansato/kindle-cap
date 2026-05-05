"""book-ocr CLI entry point."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import typer

from book_ocr import orchestrator, writer
from book_ocr.engines.yomitoku import YomiTokuEngine
from book_ocr.exporters.json_index import render_index
from book_ocr.models import BookMetadata
from book_ocr.protocols import OCREngine


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
) -> Path:
    """指定した book_dir 内の page_*.png を OCR して Markdown / index.json を出力する.

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

    engine = engine or YomiTokuEngine(
        device=device,
        reading_order=reading_order,
        ignore_meta=ignore_meta,
        chunk_size=chunk_size,
        timeout_sec=timeout_sec,
    )
    captured_at = datetime.now(UTC)
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
    pages, _index_dict_pre, book_md_str = orchestrator.run(engine, initial_meta, pngs)
    duration_sec = time.perf_counter() - t0
    finished_at = datetime.now(UTC)

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
        )
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"OCR complete: {out_path}")


def _parse_page_number(p: Path) -> int:
    """`page_NNN.png` から NNN を取り出す。issue #39 の範囲フィルタで使う。"""
    return int(p.stem.split("_")[-1])


def run_ocr() -> None:
    typer.run(ocr)
