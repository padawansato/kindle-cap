"""fixture book_dir → EPUB 生成 → 中身検証の統合テスト（外部バイナリ不要）."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from ebooklib import ITEM_DOCUMENT, ITEM_IMAGE, epub

from book_epub.cli import run_build_pipeline


def _make_full_book_dir(tmp_path: Path) -> Path:
    book_dir = tmp_path / "full-book"
    pages = book_dir / "pages"
    pages.mkdir(parents=True)
    (pages / "page_001.md").write_text("<!-- page:001 -->\n\n# 第1章\n導入", encoding="utf-8")
    (pages / "page_002.md").write_text(
        '<!-- page:002 -->\n\n<img src="../figures/page_002_figure_0.png" alt="図">\n'
        "グラフの説明ラベル",
        encoding="utf-8",
    )
    (pages / "page_003.md").write_text("<!-- page:003 -->\n\n## 1.1節\nまとめ", encoding="utf-8")
    figs = book_dir / "figures"
    figs.mkdir()
    (figs / "page_002_figure_0.png").write_bytes(b"\x89PNG fake image bytes")
    (book_dir / "index.json").write_text(json.dumps({"title": "E2E本"}), encoding="utf-8")
    (book_dir / "page_001.png").write_bytes(b"\x89PNG cover bytes")
    return book_dir


class TestEndToEnd:
    def test_generated_epub_is_valid_and_complete(self, tmp_path: Path) -> None:
        book_dir = _make_full_book_dir(tmp_path)
        epub_path = run_build_pipeline(book_dir, title=None, author="著者", out=None)

        # zip 構造: EPUB の必須要件
        with zipfile.ZipFile(epub_path) as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert zf.read("mimetype") == b"application/epub+zip"

        # ebooklib で再読込して内容検証
        book = epub.read_epub(str(epub_path))
        docs = {i.file_name for i in book.get_items_of_type(ITEM_DOCUMENT)}
        assert {"page_001.xhtml", "page_002.xhtml", "page_003.xhtml"} <= docs
        images = {i.file_name for i in book.get_items_of_type(ITEM_IMAGE)}
        assert "figures/page_002_figure_0.png" in images

        page2 = book.get_item_with_href("page_002.xhtml").get_content().decode("utf-8")
        assert 'alt="図"' in page2
        assert "グラフの説明ラベル" in page2  # 図中テキストが読み上げ対象の本文にある

        # spine 順序検証（読み上げ順序）
        spine_idrefs = [idref for idref, _ in book.spine]
        assert "nav" in spine_idrefs
        chapter_idrefs = [ref for ref in spine_idrefs if ref.startswith("chapter_")]
        assert len(chapter_idrefs) == 3
        assert chapter_idrefs == ["chapter_0", "chapter_1", "chapter_2"]
