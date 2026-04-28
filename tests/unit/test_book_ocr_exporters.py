"""book_ocr.exporters の純粋関数テスト (TDD red)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from book_ocr.exporters.book_md import render_book_md
from book_ocr.exporters.json_index import render_index
from book_ocr.exporters.page_md import render_page_md
from book_ocr.models import BookMetadata, PageText


def _make_page(
    n: int, markdown: str = "...", out_dir: Path = Path("/tmp/output/my-book")
) -> PageText:
    return PageText(
        page_number=n,
        png_path=out_dir / f"page_{n:03d}.png",
        markdown=markdown,
        ocr_engine="yomitoku",
    )


def _make_meta(page_count: int = 2) -> BookMetadata:
    return BookMetadata(
        title="my-book",
        page_count=page_count,
        captured_at=datetime(2026, 4, 28, 21, 0, 0, tzinfo=UTC),
        ocr_engine="yomitoku",
        output_dir=Path("/tmp/output/my-book"),
    )


class TestRenderPageMd:
    def test_includes_page_marker_with_zero_padding(self) -> None:
        page = _make_page(3, markdown="Hello\n")
        result = render_page_md(page)
        assert "<!-- page:003 -->" in result

    def test_includes_markdown_body(self) -> None:
        page = _make_page(1, markdown="本文の内容")
        result = render_page_md(page)
        assert "本文の内容" in result

    def test_marker_appears_before_body(self) -> None:
        page = _make_page(5, markdown="本文")
        result = render_page_md(page)
        assert result.index("<!-- page:005 -->") < result.index("本文")

    def test_handles_empty_markdown(self) -> None:
        page = _make_page(2, markdown="")
        result = render_page_md(page)
        assert "<!-- page:002 -->" in result


class TestRenderBookMd:
    def test_empty_pages_returns_empty_string(self) -> None:
        assert render_book_md([]) == ""

    def test_concatenates_pages_in_order(self) -> None:
        pages = [
            _make_page(1, "First page."),
            _make_page(2, "Second page."),
        ]
        result = render_book_md(pages)
        assert "First page." in result
        assert "Second page." in result
        assert result.index("First page.") < result.index("Second page.")

    def test_includes_page_markers_for_each_page(self) -> None:
        pages = [_make_page(1, "a"), _make_page(2, "b"), _make_page(3, "c")]
        result = render_book_md(pages)
        for n in (1, 2, 3):
            assert f"<!-- page:{n:03d} -->" in result

    def test_preserves_caller_provided_order(self) -> None:
        """sort せず、引数の順序のままで連結する (sort 責務は呼び出し側)."""
        pages = [_make_page(3, "third"), _make_page(1, "first")]
        result = render_book_md(pages)
        assert result.index("third") < result.index("first")


class TestRenderIndex:
    def test_top_level_fields(self) -> None:
        meta = _make_meta()
        pages = [_make_page(1), _make_page(2)]
        result = render_index(meta, pages)
        assert result["title"] == "my-book"
        assert result["page_count"] == 2
        assert result["ocr_engine"] == "yomitoku"

    def test_captured_at_is_iso8601(self) -> None:
        meta = _make_meta()
        result = render_index(meta, [])
        assert result["captured_at"] == "2026-04-28T21:00:00+00:00"

    def test_pages_entries_have_relative_paths(self) -> None:
        meta = _make_meta()
        pages = [_make_page(1), _make_page(2)]
        result = render_index(meta, pages)
        assert result["pages"] == [
            {"n": 1, "png": "page_001.png", "md": "pages/page_001.md"},
            {"n": 2, "png": "page_002.png", "md": "pages/page_002.md"},
        ]

    def test_pages_zero_padding_at_three_digits(self) -> None:
        meta = _make_meta(page_count=12)
        pages = [_make_page(12)]
        result = render_index(meta, pages)
        assert result["pages"][0]["md"] == "pages/page_012.md"

    def test_empty_pages_list(self) -> None:
        meta = _make_meta(page_count=0)
        result = render_index(meta, [])
        assert result["pages"] == []
        assert result["page_count"] == 0
