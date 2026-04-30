"""Render a single PageText to a Markdown string."""

from __future__ import annotations

from book_ocr.models import PageText


def render_page_md(page: PageText) -> str:
    return f"<!-- page:{page.page_number:03d} -->\n\n{page.markdown}"
