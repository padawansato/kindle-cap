"""yomitoku の JSON に対する読み順の後処理 (issue #95)。純粋関数、yomitoku 非依存。

Kindle の見開きキャプチャは 1 画像に左右 2 ページが入る。yomitoku の `--reading_order auto`
は画像全体を上下の帯で読むため、右ページの縦書きが上下 2 段に組まれていると
「右上段 → 左ページ → 右下段」の順になり、上段末尾で切れた文が下段で続くのに
その間に左ページの段落が挟まる (`docs/ocr-bench/2026-10-11-reading-order.md`)。

ここでは

1. 中央をまたぐ要素が無ければ見開きとみなし、片方のページの要素を全部読んでから
   もう片方へ進むよう `order` を振り直す。どちらが先かは縦書きが多ければ右 (rtl)、
   横書きが多ければ左 (ltr)。`page_order` で明示もできる
2. 同じページ内で読み順が隣り合う縦書き段落 A, B について、A が句点などで終わらず、
   B が A より下の段にあり、B が字下げで始まらなければ 1 段落に連結する
3. 縦書き本文の半面で、本文のどの段落よりも上にある見出しはその半面の先頭に移す
   (yomitoku はページ大見出しに遅い order を付けることがある)。横書き本文の半面は
   多段組で順序自体が崩れていることが多く、見出しだけ動かしても良くならないので触らない

`pages/page_NNN.json` 自体は書き換えない。md レンダの直前にメモリ上で適用する。
"""

from __future__ import annotations

import copy
from typing import Any

PAGE_ORDERS = ("auto", "rtl", "ltr", "off")

_TERMINAL = tuple("。．.！!？?」』）)】")
_INDENT = ("　", " ")
_CENTER_TOLERANCE = 0.02  # 画像幅に対する比。中央帯にかかる要素は「またぐ」と見なさない
_KINDS = ("paragraphs", "tables", "figures")


def _extent(raw: dict[str, Any]) -> tuple[int, int]:
    xs = [0]
    ys = [0]
    for kind in _KINDS:
        for el in raw.get(kind, []):
            xs.append(el["box"][2])
            ys.append(el["box"][3])
    for w in raw.get("words", []):
        for x, y in w.get("points", []):
            xs.append(x)
            ys.append(y)
    return int(max(xs)), int(max(ys))


def _mostly_vertical(paragraphs: list[dict[str, Any]]) -> bool:
    vertical = sum(
        len(p.get("contents", "")) for p in paragraphs if p.get("direction") == "vertical"
    )
    horizontal = sum(
        len(p.get("contents", "")) for p in paragraphs if p.get("direction") != "vertical"
    )
    return vertical > 0 and vertical >= horizontal


def _detect_rtl(groups: list[list[dict[str, Any]]]) -> bool:
    """縦書きの本なら右ページ先 (rtl)。

    ページ全体の多数決だと「右は縦書き本文、左は横書きの箇条書き」のような
    ページで負けるので、半面ごとに見て、どれかが縦書き優勢なら rtl とする
    (横書きの本に縦書き段落が半面の過半を占めることはまず無い)。"""
    return any(_mostly_vertical(g) for g in groups)


def _is_spread(elements: list[dict[str, Any]], width: int) -> bool:
    center = width / 2
    tol = width * _CENTER_TOLERANCE
    left = right = False
    for el in elements:
        x1, _, x2, _ = el["box"]
        if x1 < center - tol and x2 > center + tol:
            return False
        if x2 <= center + tol:
            left = True
        else:
            right = True
    return left and right


def _is_body_vertical(p: dict[str, Any]) -> bool:
    return p.get("direction") == "vertical" and p.get("role") is None and bool(p.get("contents"))


def _y_overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return bool(a["box"][1] < b["box"][3] and b["box"][1] < a["box"][3])


def _find_continuation(
    a: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """上段の左端で句点なしに終わる縦書き段落 A の続きを、下段の右端から探す。

    yomitoku の order は見出しなどが間に割り込むことがあるので、順序ではなく
    位置で決める。A と同じ段 (y が重なる) で A より左に縦書き段落があれば A は
    段の末尾ではないので対象外。B は A より下にある縦書き段落のうち最も上の段で、
    その段の右端のもの。"""
    if not _is_body_vertical(a) or a["contents"].endswith(_TERMINAL):
        return None
    others = [p for p in candidates if p is not a and _is_body_vertical(p)]
    if any(_y_overlaps(a, p) and p["box"][2] <= a["box"][0] for p in others):
        return None
    below = [p for p in others if p["box"][1] >= a["box"][3]]
    if not below:
        return None
    top = min(p["box"][1] for p in below)
    tier = [p for p in below if p["box"][1] < top + (p["box"][3] - p["box"][1]) * 0.5]
    b = max(tier, key=lambda p: p["box"][2])
    if b["contents"].startswith(_INDENT):
        return None
    return b


def _hoist_headings(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """縦書き本文の半面で、本文より上にある見出しを先頭へ (相対順は保つ)。"""
    body = [el for el in group if _is_body_vertical(el)]
    if not body or not _mostly_vertical([el for el in group if "contents" in el]):
        return group
    top = min(el["box"][1] for el in body)
    hoisted = [el for el in group if el.get("role") == "section_headings" and el["box"][3] <= top]
    if not hoisted:
        return group
    rest = [el for el in group if el not in hoisted]
    return hoisted + rest


def fix_reading_order(raw: dict[str, Any], *, page_order: str = "auto") -> dict[str, Any]:
    """見開きのページ順を直し、割れた縦書き段落を連結した新しい dict を返す。

    `page_order`: "auto" (縦書きが多ければ右ページ先) / "rtl" / "ltr" / "off" (何もしない)。
    """
    if page_order not in PAGE_ORDERS:
        raise ValueError(f"page_order must be one of {PAGE_ORDERS}, got {page_order!r}")
    if page_order == "off":
        return raw
    out = copy.deepcopy(raw)
    elements = [el for kind in _KINDS for el in out.get(kind, [])]
    if not elements:
        return out

    width, _height = _extent(out)
    center = width / 2
    tol = width * _CENTER_TOLERANCE
    spread = _is_spread(elements, width)

    def half(el: dict[str, Any]) -> int:
        return 0 if el["box"][2] <= center + tol else 1

    paragraphs = out.get("paragraphs", [])
    if page_order == "auto":
        groups = (
            [[p for p in paragraphs if half(p) == h] for h in (0, 1)] if spread else [paragraphs]
        )
        rtl = _detect_rtl(groups)
    else:
        rtl = page_order == "rtl"

    first = 1 if rtl else 0
    if spread:
        elements.sort(key=lambda el: (half(el) != first, el["order"]))
    else:
        elements.sort(key=lambda el: el["order"])

    # 2. 上段末尾で切れた縦書き段落を下段先頭の段落と連結する (同じページ半面に限る)
    removed: set[int] = set()
    for h in (0, 1) if spread else (None,):
        group = [p for p in paragraphs if h is None or half(p) == h]
        for a in group:
            while id(a) not in removed:
                b = _find_continuation(a, [p for p in group if id(p) not in removed])
                if b is None:
                    break
                a["contents"] = a["contents"] + "\n" + b["contents"]
                a["box"] = [
                    min(a["box"][0], b["box"][0]),
                    min(a["box"][1], b["box"][1]),
                    max(a["box"][2], b["box"][2]),
                    max(a["box"][3], b["box"][3]),
                ]
                removed.add(id(b))

    kept = [el for el in elements if id(el) not in removed]

    # 3. 縦書き本文の半面で、本文より上の見出しを先頭へ
    if spread:
        halves = [[el for el in kept if half(el) == h] for h in (first, 1 - first)]
        kept = [el for h in halves for el in _hoist_headings(h)]
    else:
        kept = _hoist_headings(kept)

    for order, el in enumerate(kept):
        el["order"] = order
    out["paragraphs"] = [p for p in paragraphs if id(p) not in removed]
    return out
