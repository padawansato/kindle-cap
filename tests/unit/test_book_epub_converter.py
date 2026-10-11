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


class TestDropReadAloudNoise:
    """読み上げ (Assistive Reader) で邪魔になるノンブル・書名の柱の段落を落とす"""

    def test_page_number_paragraphs_are_dropped_but_numbers_in_text_kept(self) -> None:
        from book_epub.converter import md_to_xhtml_body

        md = (
            "2024年に調査が行われた。\n\n014\n\n 141 \n\n０２３\n\n2026\n\n"
            "7\n\n12345\n\n寝る前の 30 分が大事だ。\n\n123\n456\n"
        )
        html = md_to_xhtml_body(md)
        assert "<p>014</p>" not in html and "141" not in html  # 3 桁・前後空白つき
        assert "０２３" not in html  # 全角数字
        assert "<p>2026</p>" not in html  # 4 桁まで
        assert "<p>12345</p>" in html  # 5 桁は残す
        assert "<p>7</p>" not in html  # 1 桁は既存の 1 文字段落除去が拾う
        assert "2024年に調査" in html and "30 分が大事" in html
        assert "123" in html and "456" in html  # 複数行の段落は対象外

    def test_numbers_in_heading_table_and_list_are_kept(self) -> None:
        from book_epub.converter import md_to_xhtml_body

        md = "# 100\n\n| 項目 | 値 |\n|---|---|\n| 歩数 | 1000 |\n\n- 200\n\n<p>300</p>\n"
        html = md_to_xhtml_body(md)
        assert "<h1>100</h1>" in html
        assert "<td>1000</td>" in html
        assert "<li>200</li>" in html
        assert "<p>300</p>" in html

    def test_running_head_matching_title_is_dropped_but_heading_kept(self) -> None:
        from book_epub.converter import md_to_xhtml_body

        title = "体調管理の本"
        md = f"# {title}\n\n{title}\n\n  {title} \n\n{title}を読む。\n\n体調管理\n"
        html = md_to_xhtml_body(md, title=title)
        assert html.count(title) == 2  # 見出しと本文中の言及だけ残る
        assert f"<h1>{title}</h1>" in html and f"{title}を読む" in html
        assert "<p>体調管理</p>" in html  # 部分一致は落とさない
        # title 未指定なら書名段落は残る
        assert f"<p>{title}</p>" in md_to_xhtml_body(md)

    def test_running_head_with_subtitle_and_kindle_chrome_labels_are_dropped(self) -> None:
        """一括 OCR 5 冊の計測 (#109): 柱は書名だけでなく副題まで続く (コードレビューの教科書
        256 枚中 148 枚、基盤モデルとロボットの融合 13 枚)。背面撮影の切り出しに Kindle の
        窓タイトル「Kindle」(125 枚) と進捗「15%」が入る。いずれも読み上げの流れを切る"""
        from book_epub.converter import md_to_xhtml_body

        title = "コードレビューの教科書"
        md = "\n\n".join(
            [
                "Kindle",
                f"{title}––なんとなく承認から抜け出すための観点と判断基準",
                f"{title}を読んだ。",  # 本文: 句点で終わる
                f"{title}" + "は" * 100,  # 本文: 長い
                "15%",
                "１００％",
                "15%の人が答えた。",
                "Kindle で読む。",
                "\\}",  # コードの閉じ括弧 (md エスケープ) は残す
            ]
        )
        html = md_to_xhtml_body(md, title=title)
        assert "なんとなく承認" not in html
        assert "<p>Kindle</p>" not in html and "<p>15%</p>" not in html and "１００％" not in html
        assert f"{title}を読んだ。" in html and "は" * 100 in html
        assert "15%の人が答えた。" in html and "Kindle で読む。" in html and "}" in html
        # 副題つきの柱は title が無いと判定できないが、Kindle の窓タイトルと進捗は title 無しでも落ちる
        html_no_title = md_to_xhtml_body(md)
        assert "なんとなく承認" in html_no_title and "<p>Kindle</p>" not in html_no_title


def test_single_char_last_line_of_multiline_paragraph_is_kept() -> None:
    """MULTILINE の `^` は段落途中の行頭にも当たり、複数行段落の最終行が 1 文字だと
    その行だけ落ちていた (#107 の調査で判明)。段落先頭は文字列先頭か空行の直後に限る"""
    from book_epub.converter import md_to_xhtml_body

    html = md_to_xhtml_body("一行目\n二行目\n三\n\n次の段落。")
    assert "三" in html and "二行目" in html
    # 単独の 1 文字段落は引き続き落ちる (文字列末尾に改行が無くても)
    assert "<p>決</p>" not in md_to_xhtml_body("本文。\n\n決")
