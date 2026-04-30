"""Render a list of PageText into a single concatenated Markdown string."""

from __future__ import annotations

from book_ocr.exporters.page_md import render_page_md
from book_ocr.models import PageText


def render_book_md(pages: list[PageText]) -> str:
    if not pages:
        return ""
    return "\n\n".join(render_page_md(p) for p in pages)
