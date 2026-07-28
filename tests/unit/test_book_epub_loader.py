"""book_epub.loader の unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from book_epub.loader import load_book


def _make_book_dir(tmp_path: Path, *, with_index: bool = True, with_figures: bool = True) -> Path:
    book_dir = tmp_path / "my-book"
    pages = book_dir / "pages"
    pages.mkdir(parents=True)
    (pages / "page_001.md").write_text("<!-- page:001 -->\n\n# 第1章\n本文1", encoding="utf-8")
    (pages / "page_002.md").write_text(
        '<!-- page:002 -->\n\n<img src="../figures/page_002_figure_0.png" alt="図">\n図中の文',
        encoding="utf-8",
    )
    if with_index:
        (book_dir / "index.json").write_text(
            json.dumps({"title": "実タイトル"}), encoding="utf-8"
        )
    if with_figures:
        figs = book_dir / "figures"
        figs.mkdir()
        (figs / "page_002_figure_0.png").write_bytes(b"png")
    (book_dir / "page_001.png").write_bytes(b"cover")
    return book_dir


class TestLoadBook:
    def test_loads_pages_sorted_with_marker_stripped(self, tmp_path: Path) -> None:
        source, warnings = load_book(_make_book_dir(tmp_path))
        assert [p.page_number for p in source.pages] == [1, 2]
        assert source.pages[0].markdown.startswith("# 第1章")
        assert warnings == []

    def test_title_priority_override_then_index(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        assert load_book(book_dir)[0].title == "実タイトル"
        assert load_book(book_dir, title_override="上書き")[0].title == "上書き"

    def test_title_falls_back_to_dirname_with_warning(self, tmp_path: Path) -> None:
        source, warnings = load_book(_make_book_dir(tmp_path, with_index=False))
        assert source.title == "my-book"
        assert any("index.json" in w for w in warnings)

    def test_missing_figures_dir_warns(self, tmp_path: Path) -> None:
        source, warnings = load_book(_make_book_dir(tmp_path, with_figures=False))
        assert source.figures_dir is None
        assert any("figures" in w for w in warnings)

    def test_missing_pages_dir_raises_with_guidance(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="book-ocr"):
            load_book(empty)

    def test_cover_png_detected(self, tmp_path: Path) -> None:
        source, _ = load_book(_make_book_dir(tmp_path))
        assert source.cover_png is not None
        assert source.cover_png.name == "page_001.png"
