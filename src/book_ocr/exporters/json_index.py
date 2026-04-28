"""Render BookMetadata + pages into a JSON-serialisable index dict."""

from __future__ import annotations

from typing import Any

from book_ocr.models import BookMetadata, PageText


def render_index(meta: BookMetadata, pages: list[PageText]) -> dict[str, Any]:
    return {
        "title": meta.title,
        "page_count": meta.page_count,
        "captured_at": meta.captured_at.isoformat(),
        "ocr_engine": meta.ocr_engine,
        "pages": [
            {
                "n": p.page_number,
                "png": p.png_path.relative_to(meta.output_dir).as_posix(),
                "md": f"pages/page_{p.page_number:03d}.md",
            }
            for p in pages
        ],
    }
