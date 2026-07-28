"""book_epub.builder の unit tests."""

from __future__ import annotations

from pathlib import Path

from ebooklib import ITEM_DOCUMENT, ITEM_IMAGE

from book_epub.builder import build_epub, build_toc
from book_epub.converter import Heading
from book_epub.loader import BookSource, SourcePage


def _source(tmp_path: Path, *, with_figures: bool = True) -> BookSource:
    figures_dir = None
    if with_figures:
        figures_dir = tmp_path / "figures"
        figures_dir.mkdir()
        (figures_dir / "page_002_figure_0.png").write_bytes(b"\x89PNG fake")
    cover = tmp_path / "page_001.png"
    cover.write_bytes(b"\x89PNG cover")
    return BookSource(
        book_dir=tmp_path,
        title="テスト本",
        pages=[
            SourcePage(1, "# 第1章\n本文1"),
            SourcePage(2, '<img src="../figures/page_002_figure_0.png" alt="図">\n図中の文'),
        ],
        figures_dir=figures_dir,
        cover_png=cover,
    )


class TestBuildToc:
    def test_nests_level2_under_level1(self) -> None:
        toc = build_toc(
            [
                (Heading(1, "第1章"), "page_001.xhtml"),
                (Heading(2, "1.1節"), "page_002.xhtml"),
                (Heading(1, "第2章"), "page_003.xhtml"),
            ]
        )
        assert len(toc) == 2  # 第1章(子持ち), 第2章
        section, children = toc[0]
        assert section.title == "第1章"
        assert children[0].title == "1.1節"

    def test_orphan_level2_becomes_top_level(self) -> None:
        toc = build_toc([(Heading(2, "いきなり節"), "page_001.xhtml")])
        assert len(toc) == 1

    def test_empty(self) -> None:
        assert build_toc([]) == []


class TestBuildEpub:
    def test_spine_contains_all_pages_in_order(self, tmp_path: Path) -> None:
        book, warnings = build_epub(_source(tmp_path))
        chapter_names = [item.file_name for item in book.get_items_of_type(ITEM_DOCUMENT)]
        assert "page_001.xhtml" in chapter_names
        assert "page_002.xhtml" in chapter_names
        assert warnings == []

    def test_figure_embedded_with_alt(self, tmp_path: Path) -> None:
        book, _ = build_epub(_source(tmp_path))
        image_names = [i.file_name for i in book.get_items_of_type(ITEM_IMAGE)]
        assert "figures/page_002_figure_0.png" in image_names
        page2 = book.get_item_with_href("page_002.xhtml")
        content = page2.get_content().decode("utf-8")
        assert '<img src="figures/page_002_figure_0.png" alt="図"/>' in content
        assert "図中の文" in content

    def test_missing_figure_ref_skipped_with_warning(self, tmp_path: Path) -> None:
        src = _source(tmp_path, with_figures=False)
        book, warnings = build_epub(src)
        page2 = book.get_item_with_href("page_002.xhtml")
        content = page2.get_content().decode("utf-8")
        assert "<img" not in content
        assert "図中の文" in content  # 本文テキストは維持
        assert any("page_002_figure_0.png" in w for w in warnings)

    def test_pagebreak_marker_present(self, tmp_path: Path) -> None:
        book, _ = build_epub(_source(tmp_path))
        content = book.get_item_with_href("page_001.xhtml").get_content().decode("utf-8")
        assert 'epub:type="pagebreak"' in content
        assert 'id="page_001"' in content

    def test_metadata_and_cover(self, tmp_path: Path) -> None:
        book, _ = build_epub(_source(tmp_path), author="著者名")
        assert book.title == "テスト本"
        assert book.language == "ja"
        cover_items = [i for i in book.get_items() if i.file_name == "cover.png"]
        assert cover_items

    def test_toc_falls_back_to_single_entry_when_no_headings(self, tmp_path: Path) -> None:
        src = BookSource(
            book_dir=tmp_path,
            title="無見出し本",
            pages=[SourcePage(1, "本文のみ")],
            figures_dir=None,
            cover_png=None,
        )
        book, _ = build_epub(src)
        assert len(book.toc) == 1
        assert book.toc[0].title == "無見出し本"
