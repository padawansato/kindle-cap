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


class TestDropSingleCharParagraphs:
    """issue #68: 縦書きの装飾見出し「解決法」が「決」「法」の 1 文字段落になる"""

    def test_single_char_paragraphs_are_dropped_but_real_text_kept(self) -> None:
        from book_epub.converter import md_to_xhtml_body

        md = "眠れなくなることも少なくありません。\n\n決\n\n法\n\n# 質のいい睡眠を取る\n\n解 \n\n寝室を再考する。\n\n●\n"
        html = md_to_xhtml_body(md)
        assert "<p>決</p>" not in html and "<p>法</p>" not in html and "<p>解</p>" not in html
        assert "<p>●</p>" not in html  # 記号 1 文字も同様
        assert "少なくありません" in html and "寝室を再考する" in html
        assert "<h1>質のいい睡眠を取る</h1>" in html  # 見出しは対象外

    def test_single_char_line_inside_a_paragraph_is_not_touched(self) -> None:
        from book_epub.converter import md_to_xhtml_body

        # 空行で区切られていない行は段落の一部なので落とさない
        html = md_to_xhtml_body("一\n二\n三")
        assert "一" in html and "二" in html and "三" in html


class TestReadAloudNormalization:
    """読み上げ (Assistive Reader) の邪魔になるノンブルと柱を落とす"""

    def test_page_number_paragraphs_are_dropped_but_real_content_kept(self) -> None:
        from book_epub.converter import md_to_xhtml_body

        md = (
            "本文です。\n\n014\n\n２０２\n\n  015  \n\n2024年に始まった。\n\n"
            "5\n\n12345\n\n| a | b |\n|---|---|\n| 100 | 200 |\n\n"
            "- 300\n- 400\n\n<p>500</p>\n\n# 600\n\n本文\n123\n"
        )
        html = md_to_xhtml_body(md)
        for gone in ("<p>014</p>", "<p>２０２</p>", "<p>015</p>"):
            assert gone not in html
        assert "2024年に始まった" in html
        assert "12345" in html  # 5 桁は年号・金額などの可能性があり対象外
        assert "<td>100</td>" in html and "<li>300</li>" in html  # 表・リスト
        assert "<p>500</p>" in html and "<h1>600</h1>" in html
        assert "123" in html  # 段落内の 1 行は段落の一部

    def test_running_head_equal_to_title_is_dropped_but_heading_kept(self) -> None:
        from book_epub.converter import md_to_xhtml_body

        md = "# 体調管理の本\n\n体調管理の本\n\n 体調管理の本 \n\n体調管理の本を読む。\n"
        html = md_to_xhtml_body(md, title="体調管理の本")
        assert "<h1>体調管理の本</h1>" in html
        assert "<p>体調管理の本</p>" not in html
        assert "体調管理の本を読む" in html
        # title 未指定なら何も落とさない
        assert "<p>体調管理の本</p>" in md_to_xhtml_body(md)
