"""OCR 結果を出力ディレクトリに書き出す I/O 層."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from book_ocr.exporters.page_md import render_page_md
from book_ocr.models import PageText


def write_outputs(
    out_dir: Path,
    book_md_filename: str,
    index: dict[str, Any],
    book_md: str,
    pages: list[PageText],
) -> None:
    """index.json / <book>.md / pages/page_NNN.md を out_dir 配下に書き出す.

    out_dir が無ければ作成する (parents=True)。pages が空の場合は pages/
    サブディレクトリを作らない。日本語タイトルは Unicode escape せずに
    そのまま JSON に書く。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / book_md_filename).write_text(book_md, encoding="utf-8")

    if pages:
        pages_dir = out_dir / "pages"
        pages_dir.mkdir(exist_ok=True)
        for page in pages:
            (pages_dir / f"page_{page.page_number:03d}.md").write_text(
                render_page_md(page), encoding="utf-8"
            )
