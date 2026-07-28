"""book_epub.converter の unit tests."""

from __future__ import annotations

from book_epub.converter import Heading, extract_headings, md_to_xhtml_body, normalize_figure_srcs


class TestMdToXhtmlBody:
    def test_paragraph_and_heading(self) -> None:
        html = md_to_xhtml_body("# 第1章\n\n本文です。")
        assert "<h1>第1章</h1>" in html
        assert "<p>本文です。</p>" in html

    def test_html_table_passthrough(self) -> None:
        # yomitoku は表を html <table> で md に埋め込む。素通しされること
        md = "<table><tr><td>セル</td></tr></table>"
        assert "<table>" in md_to_xhtml_body(md)


class TestNormalizeFigureSrcs:
    def test_parent_relative_src_normalized(self) -> None:
        html = '<img src="../figures/page_003_figure_0.png" alt="図">'
        result = normalize_figure_srcs(html)
        assert '<img src="figures/page_003_figure_0.png" alt="図"/>' in result

    def test_root_relative_src_kept_and_self_closed(self) -> None:
        html = '<img src="figures/page_001_figure_0.png" alt="図">'
        assert normalize_figure_srcs(html) == '<img src="figures/page_001_figure_0.png" alt="図"/>'


class TestExtractHeadings:
    def test_levels_1_to_3_extracted_in_order(self) -> None:
        md = "# 章\n本文\n## 節\n### 項\n#### 深すぎ\n"
        assert extract_headings(md) == [
            Heading(1, "章"),
            Heading(2, "節"),
            Heading(3, "項"),
        ]

    def test_no_headings(self) -> None:
        assert extract_headings("本文のみ") == []
