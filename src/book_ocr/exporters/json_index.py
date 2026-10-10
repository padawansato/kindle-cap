"""Render BookMetadata + pages into a JSON-serialisable index dict."""

from __future__ import annotations

from typing import Any

from book_ocr.models import BookMetadata, PageText


def render_index(meta: BookMetadata, pages: list[PageText]) -> dict[str, Any]:
    """index.json に書き出す dict を組み立てる.

    `png` フィールドはファイル名のみ (例 "page_001.png")。kindle-cap の出力規約上、
    PNG は単一ディレクトリに並ぶので、ディレクトリ構造を保持する必要がない。
    book_dir != output_dir (--out 指定時) でも relative_to の ValueError を踏まない。

    issue #40: `ocr_engine_version` / `ocr_settings` / `ocr_runtime` が
    `BookMetadata` に設定されていれば additive に追記する (None なら省略)。
    """
    result: dict[str, Any] = {
        "title": meta.title,
        "page_count": meta.page_count,
        "captured_at": meta.captured_at.isoformat(),
        "ocr_engine": meta.ocr_engine,
    }
    if meta.ocr_engine_version is not None:
        result["ocr_engine_version"] = meta.ocr_engine_version
    if meta.ocr_settings is not None:
        result["ocr_settings"] = meta.ocr_settings
    if meta.ocr_runtime is not None:
        result["ocr_runtime"] = meta.ocr_runtime
    if meta.searchable_pdf is not None:
        result["searchable_pdf"] = meta.searchable_pdf
    result["pages"] = [_render_page_entry(p) for p in pages]
    return result


def _render_page_entry(page: PageText) -> dict[str, Any]:
    """1 ページ分のエントリ。`json` は生 JSON を持つページにだけ additive に載せる.

    issue #70: `--skip-existing` で md だけから復元したページは JSON を持たないので、
    キーの有無で「searchable PDF を作れるページか」が判別できる。
    """
    entry: dict[str, Any] = {
        "n": page.page_number,
        "png": page.png_path.name,
        "md": f"pages/page_{page.page_number:03d}.md",
    }
    if page.json_path is not None:
        entry["json"] = f"pages/page_{page.page_number:03d}.json"
    return entry
