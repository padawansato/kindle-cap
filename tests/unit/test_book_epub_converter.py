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

    def test_br_between_japanese_text_is_removed_without_space(self) -> None:
        # yomitoku は原本の行折り返し位置を <br> として本文に埋め込む（レイアウト由来の強制改行）
        html = md_to_xhtml_body("考えから抜け<br>出せなくなる")
        assert "<p>考えから抜け出せなくなる</p>" in html
        assert "<br" not in html

    def test_br_between_ascii_words_becomes_space(self) -> None:
        html = md_to_xhtml_body("Robotics<br>by")
        assert "<p>Robotics by</p>" in html
        assert "<br" not in html

    def test_self_closing_br_variants_removed(self) -> None:
        for tag in ("<br/>", "<br />"):
            html = md_to_xhtml_body(f"抜け{tag}出せなく")
            assert "抜け出せなく" in html
            assert "<br" not in html

    def test_text_without_br_is_unchanged(self) -> None:
        html = md_to_xhtml_body("本文です。")
        assert "<p>本文です。</p>" in html


class TestNormalizeFigureSrcs:
    def test_parent_relative_src_normalized(self) -> None:
        html = '<img src="../figures/page_003_figure_0.png" alt="図">'
        result = normalize_figure_srcs(html)
        assert '<img src="figures/page_003_figure_0.png" alt="図"/>' in result

    def test_root_relative_src_kept_and_self_closed(self) -> None:
        html = '<img src="figures/page_001_figure_0.png" alt="図">'
        assert normalize_figure_srcs(html) == '<img src="figures/page_001_figure_0.png" alt="図"/>'

    def test_alt_before_src_attribute_order_normalized(self) -> None:
        # Markdown-Python が生成する <img alt="..." src="..."> にも対応（属性順序に依存しない）
        html = '<img alt="図" src="../figures/page_003_figure_0.png" />'
        result = normalize_figure_srcs(html)
        assert 'src="figures/page_003_figure_0.png"' in result
        assert "../" not in result
        assert 'alt="図"' in result

    def test_markdown_generated_img_with_alt_before_src(self) -> None:
        # md_to_xhtml_body 結果（![図](../figures/...)）を normalize_figure_srcs で処理
        md = "![図](../figures/page_003_figure_0.png)"
        html = md_to_xhtml_body(md)
        normalized = normalize_figure_srcs(html)
        assert 'src="figures/page_003_figure_0.png"' in normalized
        assert "../" not in normalized


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

    def test_br_tag_removed_from_heading_text(self) -> None:
        # yomitoku の md 見出しは行内改行が <br> として埋め込まれることがある
        md = "# ちょっとしたことでうまくいく<br>発達障害の人が\n"
        assert extract_headings(md) == [Heading(1, "ちょっとしたことでうまくいく発達障害の人が")]

    def test_multiple_br_tags_removed(self) -> None:
        md = "# は<br>じ<br>め<br>に\n"
        assert extract_headings(md) == [Heading(1, "はじめに")]

    def test_heading_that_becomes_empty_after_tag_removal_is_excluded(self) -> None:
        md = "# <br>\n本文\n## 節\n"
        assert extract_headings(md) == [Heading(2, "節")]
