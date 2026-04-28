"""書籍単位の OCR 実行を束ねる薄いグルー (副作用なし)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from book_ocr.exporters.book_md import render_book_md
from book_ocr.exporters.json_index import render_index
from book_ocr.models import BookMetadata, PageText
from book_ocr.protocols import OCREngine


def run(
    engine: OCREngine,
    meta: BookMetadata,
    png_paths: list[Path],
) -> tuple[list[PageText], dict[str, Any], str]:
    """各 PNG に対して engine を呼び出し、ページ・index dict・全文 Markdown を返す.

    副作用なし。ディスク書き込みは writer.py が担う。
    """
    pages = engine.run_batch(png_paths)

    seen: set[int] = set()
    for page in pages:
        if page.page_number in seen:
            raise ValueError(
                f"duplicate page_number {page.page_number} returned by engine"
            )
        seen.add(page.page_number)

    index = render_index(meta, pages)
    book_md = render_book_md(pages)
    return pages, index, book_md
