"""book_ocr.reading_order (issue #95): 見開きのページ順と、縦書き 2 段組で割れた段落の連結."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from book_ocr.reading_order import fix_reading_order

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "spread_vertical_two_tier.json"


def _load() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _by_order(raw: dict[str, Any]) -> list[tuple[str, int, dict[str, Any]]]:
    items = [("p", p["order"], p) for p in raw["paragraphs"]]
    items += [("t", t["order"], t) for t in raw["tables"]]
    items += [("f", f["order"], f) for f in raw["figures"]]
    return sorted(items, key=lambda x: x[1])


def test_vertical_spread_reads_right_page_first_and_joins_split_paragraph() -> None:
    """実書籍 page_009 (右: 縦書き上下 2 段、左: 横書き) の構造そのまま。

    yomitoku は上段 → 左ページ → 下段の順にし、上段末尾「…実」と下段先頭「際に障」が
    別段落になる。右ページ (縦書き = rtl) を全部読んでから左ページへ進み、
    割れた段落は連結する。"""
    raw = _load()
    before_paragraphs = len(raw["paragraphs"])
    fixed = fix_reading_order(raw, page_order="auto")

    seq = _by_order(fixed)
    # order は 0 から隙間なく振り直される
    assert [o for _, o, _ in seq] == list(range(len(seq)))
    # 右ページ (x > 中央) の要素が先、左ページが後
    halves = [el["box"][0] > 1400 for _, _, el in seq]
    assert halves == sorted(halves, reverse=True)
    # 「…実」+「際に障」が 1 段落になり、段落数が 1 減る
    assert len(fixed["paragraphs"]) == before_paragraphs - 1
    joined = next(p for p in fixed["paragraphs"] if "\n際に障" in p["contents"])
    assert joined["contents"].startswith("発達障…って実\n際に障")
    assert joined["contents"].endswith("せん。")
    assert joined["box"] == [1621, 397, 2719, 1560]  # 両方の box の和
    # 右ページは上端の大見出しが先頭に来て、本文は元の順序 (0,1,2,3,4+20,21,22) を保つ
    right = [p["contents"][:3] for _, _, p in seq if p["box"][0] > 1400 and "contents" in p]
    assert right[:5] == ["発達障", "本書で", "発達障", "発達障", "ADH"]
    # 入力は壊さない
    assert raw == _load()


def test_horizontal_spread_reads_left_page_first() -> None:
    raw = _load()
    for p in raw["paragraphs"]:
        p["direction"] = "horizontal"
    fixed = fix_reading_order(raw, page_order="auto")
    halves = [el["box"][0] > 1400 for _, _, el in _by_order(fixed)]
    assert halves == sorted(halves)  # 左 (False) が先
    assert len(fixed["paragraphs"]) == len(raw["paragraphs"])  # 横書きは連結しない


def test_explicit_page_order_overrides_detection_and_off_is_identity() -> None:
    raw = _load()
    ltr = fix_reading_order(raw, page_order="ltr")
    assert next(el["box"][0] > 1400 for _, _, el in _by_order(ltr)) is False
    assert fix_reading_order(raw, page_order="off") == raw
    with pytest.raises(ValueError):
        fix_reading_order(raw, page_order="sideways")


def test_single_page_is_left_untouched_except_tier_join() -> None:
    """中央をまたぐ要素があれば見開きではない。ページ順の入れ替えはしないが、
    縦書き段落の連結 (上下段) は位置で決めるのでページ順と無関係に起きる"""
    raw = _load()
    raw["paragraphs"].append(
        {
            "box": [1000, 1600, 1800, 1650],
            "contents": "中央をまたぐ。",
            "direction": "horizontal",
            "order": 99,
            "role": None,
        }
    )
    fixed = fix_reading_order(raw, page_order="auto")
    seq = _by_order(fixed)
    assert [o for _, o, _ in seq] == list(range(len(seq)))
    # 要素の相対順は yomitoku のまま (ページ順の入れ替え無し)。連結された
    # 「際に障」だけが消え、「…実」の box は和になる
    expected = [
        el for _, _, el in _by_order(raw) if not el.get("contents", "").startswith("際に障")
    ]
    assert len(seq) == len(expected)
    for (_, _, got), want in zip(seq, expected, strict=True):
        if want.get("contents", "").endswith("って実"):
            assert got["contents"].startswith(want["contents"] + "\n際に障")
        else:
            assert got["box"] == want["box"]
    assert len(fixed["paragraphs"]) == len(raw["paragraphs"]) - 1


@pytest.mark.parametrize(
    ("a_tail", "b_head", "a_role", "joined"),
    [
        ("…実", "際に障", None, True),
        ("…す。", "際に障", None, False),  # 句点で終わる
        ("…実", "　際に障", None, False),  # 全角スペース = 新しい段落
        ("…実", "際に障", "section_headings", False),  # 見出しは連結しない
    ],
)
def test_join_guards(a_tail: str, b_head: str, a_role: str | None, joined: bool) -> None:
    raw = {
        "paragraphs": [
            {
                "box": [1600, 400, 1700, 900],
                "contents": a_tail,
                "direction": "vertical",
                "order": 0,
                "role": a_role,
            },
            {
                "box": [2600, 1000, 2700, 1500],
                "contents": b_head,
                "direction": "vertical",
                "order": 1,
                "role": None,
            },
            {
                "box": [100, 400, 1300, 500],
                "contents": "左ページ。",
                "direction": "horizontal",
                "order": 2,
                "role": None,
            },
        ],
        "tables": [],
        "figures": [],
        "words": [{"points": [[0, 0], [2800, 0], [2800, 1600], [0, 1600]]}],
    }
    fixed = fix_reading_order(copy.deepcopy(raw), page_order="rtl")
    assert (len(fixed["paragraphs"]) == 2) is joined


def test_page_heading_above_vertical_body_moves_to_front_of_its_half() -> None:
    """右ページ上端の大見出し「発達障害の種類」は yomitoku の order が 18 で、本文
    5 段落目の後に来ていた。縦書き本文の半面では、本文より上にある見出しを先頭へ。
    横書きの左ページ (多段組で順序自体が崩れている) には手を付けない"""
    raw = _load()
    fixed = fix_reading_order(raw, page_order="auto")
    seq = [el for _, _, el in _by_order(fixed)]
    right = [el for el in seq if el["box"][0] > 1400]
    assert right[0].get("role") == "section_headings"
    assert right[0]["contents"].startswith("発達障")
    assert right[1]["contents"].startswith("本書で")  # 本文はその後に元の順で続く
    # 左ページは元の相対順のまま (特徴/ADHD の見出しは動かさない)
    left_before = [
        el["contents"][:3]
        for _, _, el in _by_order(raw)
        if el["box"][0] <= 1400 and "contents" in el
    ]
    left_after = [el["contents"][:3] for el in seq if el["box"][0] <= 1400 and "contents" in el]
    assert left_after == left_before
