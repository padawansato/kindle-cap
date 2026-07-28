"""Render a single PageText to a Markdown string."""

from __future__ import annotations

from book_ocr.models import PageText


def render_page_md(page: PageText) -> str:
    # PageText.markdown 内の図参照は book_dir 直下基準 (figures/)。
    # pages/ 配下に置く page md では ../figures/ に補正する
    body = page.markdown.replace('src="figures/', 'src="../figures/')
    return f"<!-- page:{page.page_number:03d} -->\n\n{body}"
