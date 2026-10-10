"""リーダー画面での先頭移動と綴じ方向の判定.

Kindle.app (新版) は URL スキームやメニューで「先頭へ」ができないので、
前ページキーをスクリーンショットの md5 が変わらなくなるまで送って先頭に戻す。
どちらのキーが「前」かは、chrome 表示時に出るステータス文
`"N ページ中の M ページ目 · …"` の M の増減で判断する。表紙ページにはステータス文が
無い (None) ことも手がかりにする。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from .config import Direction

logger = logging.getLogger(__name__)

KEY_LEFT = 123
KEY_RIGHT = 124

# 固定ページの本: "323ページ中の3ページ目 · …"  / 位置番号の本 (小説など): "位置No. 24/30 · 82%"
_STATUS_PAGE_RE = re.compile(r"(\d+)ページ中の(\d+)ページ目")
_STATUS_LOC_RE = re.compile(r"位置\s*No\.?\s*(\d+)\s*/\s*(\d+)")

Status = tuple[int, int]  # (総ページ数, 現在ページ)


def parse_status(text: str | None) -> Status | None:
    if not text:
        return None
    if m := _STATUS_PAGE_RE.search(text):
        return (int(m.group(1)), int(m.group(2)))
    if m := _STATUS_LOC_RE.search(text):
        return (int(m.group(2)), int(m.group(1)))
    return None


def _direction_for_prev(prev_key: int) -> Direction:
    """kindle_cap.keys の対応 (RTL → 次=右キー) に合わせる。前が左なら次は右 → RTL。"""
    return Direction.RTL if prev_key == KEY_LEFT else Direction.LTR


def _guess_prev_key(readings: list[Status | None]) -> int | None:
    """左キーを押しながら読んだステータス列から「前ページ」キーを推定する.

    ステータスが読めた 2 点の増減で決める (表紙や図版ページは None なので飛ばす)。
    1 点しか読めず、先頭 (表紙) が None なら「表紙 → 本文に進んだ = 左は次」。"""
    known = [r for r in readings if r is not None]
    if len(known) >= 2:
        a, b = known[-2], known[-1]
        if b[1] < a[1]:
            return KEY_LEFT
        if b[1] > a[1]:
            return KEY_RIGHT
        return None
    if readings and readings[0] is None and len(known) == 1:
        return KEY_RIGHT  # 表紙 (ステータス無し) → 本文: 左は「次」だった
    if readings and readings[0] is not None and len(known) == 1 and readings[-1] is None:
        return KEY_LEFT  # 本文 → 表紙: 左は「前」だった
    return None


def rewind_to_start(
    *,
    press: Callable[[int], None],
    page_hash: Callable[[], str],
    read_status: Callable[[], Status | None],
    sleeper: Callable[[float], None],
    wait: float,
    max_presses: int = 3000,
) -> Direction:
    """本の先頭まで戻し、撮影に使う綴じ方向を返す.

    1. 左キーを数回押してステータス文の増減から前/次を推定できれば、前キーを
       画面が変わらなくなるまで送る。
    2. 推定できなければ、まず左キーで左端まで行き、そこでのステータス文が無い
       (表紙) か前半なら先頭、後半なら末尾とみなして右端まで戻す。
    """
    pressed = 0

    def press_until_stable(key: int) -> None:
        nonlocal pressed
        last = page_hash()
        while True:
            if pressed >= max_presses:
                raise RuntimeError(
                    f"{max_presses} 回押しても先頭に着きません (キー {key})。"
                    "Kindle にフォーカスが無いかページ送りが効いていません"
                )
            press(key)
            pressed += 1
            sleeper(wait)
            current = page_hash()
            if current == last:
                return
            last = current

    readings: list[Status | None] = [read_status()]
    for _ in range(4):
        press(KEY_LEFT)
        pressed += 1
        sleeper(wait)
        readings.append(read_status())
        if sum(r is not None for r in readings) >= 2:
            break
    prev_key = _guess_prev_key(readings)
    if prev_key is not None:
        logger.debug("前ページキー=%s (ステータス %s)", prev_key, readings)
        press_until_stable(prev_key)
        return _direction_for_prev(prev_key)

    press_until_stable(KEY_LEFT)
    status = read_status()
    at_beginning = status is None or status[1] * 2 <= status[0]
    logger.debug("左端のステータス %s → %s", status, "先頭" if at_beginning else "末尾")
    if at_beginning:
        return _direction_for_prev(KEY_LEFT)
    press_until_stable(KEY_RIGHT)
    return _direction_for_prev(KEY_RIGHT)
