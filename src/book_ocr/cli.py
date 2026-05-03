"""book-ocr CLI entry point."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from book_ocr import orchestrator, writer
from book_ocr.engines.yomitoku import YomiTokuEngine
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
) -> Path:
    """指定した book_dir 内の page_*.png を OCR して Markdown / index.json を出力する.

    `engine=None` のときは `YomiTokuEngine` を生成する。テストでは FakeEngine 等を渡す。

    Returns:
        生成された book Markdown ファイルのパス。
    """
    pngs = sorted(book_dir.glob("page_*.png"))
    if not pngs:
        raise FileNotFoundError(f"No page_*.png in {book_dir}")

    title = name or book_dir.name
    out_dir = out or book_dir

    engine = engine or YomiTokuEngine(
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

    pages, index_dict, book_md_str = orchestrator.run(engine, meta, pngs)
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
        )
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"OCR complete: {out_path}")


def run_ocr() -> None:
    typer.run(ocr)
