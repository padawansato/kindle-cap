"""book-ocr CLI entry point."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from book_ocr import orchestrator, writer
from book_ocr.engines.yomitoku import YomiTokuEngine
from book_ocr.models import BookMetadata
from book_ocr.protocols import OCREngine


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
) -> None:
    """指定した book_dir 内の page_*.png を OCR して Markdown / index.json を生成する."""
    pngs = sorted(book_dir.glob("page_*.png"))
    if not pngs:
        typer.echo(f"No page_*.png in {book_dir}", err=True)
        raise typer.Exit(1)

    title = name or book_dir.name
    out_dir = out or book_dir

    engine = YomiTokuEngine(
        device=device,
        reading_order=reading_order,
        ignore_meta=ignore_meta,
    )
    meta = BookMetadata(
        title=title,
        page_count=len(pngs),
        captured_at=datetime.now(UTC),
        ocr_engine=engine.name,
        output_dir=out_dir,
    )

    _run(engine, meta, pngs, out_dir, book_md_filename=f"{title}.md")
    typer.echo(f"OCR complete: {out_dir}/{title}.md")


def _run(
    engine: OCREngine,
    meta: BookMetadata,
    png_paths: list[Path],
    out_dir: Path,
    book_md_filename: str,
) -> None:
    """テストから直接呼べる engine 注入ポイント."""
    pages, index_dict, book_md_str = orchestrator.run(engine, meta, png_paths)
    writer.write_outputs(
        out_dir=out_dir,
        book_md_filename=book_md_filename,
        index=index_dict,
        book_md=book_md_str,
        pages=pages,
    )


def run_ocr() -> None:
    typer.run(ocr)
