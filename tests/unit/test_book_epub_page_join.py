"""book_epub.page_join の unit tests."""

from __future__ import annotations

from book_epub.loader import SourcePage
from book_epub.page_join import join_cross_page_sentences


def _pages(*markdowns: str, start: int = 1) -> list[SourcePage]:
    return [SourcePage(start + i, md) for i, md in enumerate(markdowns)]


def _texts(pages: list[SourcePage]) -> list[str]:
    return [p.markdown for p in pages]


def test_sentence_cut_at_page_end_is_joined_with_next_page_head() -> None:
    pages = _pages(
        "# 見出し\n\n前の段落。\n\nページ末尾で切れ<br>た文の前半",
        "後半はここに続く。\n\n次の段落。",
    )
    result = join_cross_page_sentences(pages)
    assert _texts(result) == [
        "# 見出し\n\n前の段落。\n\nページ末尾で切れ<br>た文の前半後半はここに続く。",
        "次の段落。",
    ]
    # page_number は保たれ、入力は変更されない
    assert [p.page_number for p in result] == [1, 2]
    assert pages[1].markdown == "後半はここに続く。\n\n次の段落。"


def test_not_joined_when_previous_ends_with_terminator_or_next_is_not_plain() -> None:
    cases = [
        ("文が終わっている。", "次の文"),
        ("会話が閉じている」", "次の文"),
        ("Done.", "next"),
        ("全角括弧が閉じている）", "次の文"),
        ("途中の文", "# 見出し"),
        ("途中の文", "　字下げで始まる新しい段落"),
        ("途中の文", " 半角字下げ"),
        ("途中の文", "・箇条書き"),
        ("途中の文", "「会話」"),
        ("途中の文", "（注）"),
        ("途中の文", "- リスト"),
        ("途中の文", "1. 番号付き"),
        ("途中の文", "| a | b |"),
        ("途中の文", '<img src="../figures/page_002_figure_0.png" alt="図">'),
        ("途中の文", "<table><tr><td>x</td></tr></table>"),
        ("## 見出しで終わる", "本文"),
        ("- リストで終わる", "本文"),
        ('<img src="../figures/page_001_figure_0.png" alt="図">', "本文"),
        # 1 文字だけのブロックは縦書き装飾見出しの断片 (converter が落とす) なので結合しない
        ("決", "法を見直す"),
        ("途中の文", "法"),
        # 数字と記号だけのブロックはノンブル (ページ番号) なので本文と連結しない
        ("運動が継続しない人は、「疲れ\n\n134", "ているから明日から」"),
        ("途中の文", "– 12 –"),
        ("途中の文", ""),
        ("", "本文"),
    ]
    for prev, nxt in cases:
        pages = _pages(prev, nxt)
        assert _texts(join_cross_page_sentences(pages)) == [prev, nxt], (prev, nxt)


def test_not_joined_across_skipped_page_numbers() -> None:
    pages = [SourcePage(3, "途中の文"), SourcePage(5, "続き。")]
    assert _texts(join_cross_page_sentences(pages)) == ["途中の文", "続き。"]


def test_ascii_boundary_gets_a_space_and_emptied_page_is_kept() -> None:
    pages = _pages("the quick brown", "fox jumps.", "次のページ。")
    result = join_cross_page_sentences(pages)
    assert _texts(result) == ["the quick brown fox jumps.", "", "次のページ。"]
    assert [p.page_number for p in result] == [1, 2, 3]


def test_join_happens_once_per_pair_without_chaining() -> None:
    # 各組は結合後の状態で 1 回だけ判定する。2 の残りブロックは 2→3 の組として結合される
    pages = _pages("一ページ目の途中", "二ページ目の頭\n\n二ページ目の途中", "三ページ目の頭。")
    assert _texts(join_cross_page_sentences(pages)) == [
        "一ページ目の途中二ページ目の頭",
        "二ページ目の途中三ページ目の頭。",
        "",
    ]
    # 2 が丸ごと 1 に取り込まれて空になっても、1 の末尾が 3 の先頭まで取り込むことはない
    pages = _pages("一ページ目の途中", "二ページ目の全部", "三ページ目の頭。")
    assert _texts(join_cross_page_sentences(pages)) == [
        "一ページ目の途中二ページ目の全部",
        "",
        "三ページ目の頭。",
    ]
