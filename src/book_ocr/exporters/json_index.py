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
    result["pages"] = [
        {
            "n": p.page_number,
            "png": p.png_path.name,
            "md": f"pages/page_{p.page_number:03d}.md",
        }
        for p in pages
    ]
    return result
