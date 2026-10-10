"""Kindle.app のライブラリ画面から書籍を列挙し、本を開く / 閉じる.

ライブラリの各書籍は AXButton で、description が
`"タイトル, 著者, 既読|NEW|PDF|サンプル, "`、value が
`"本がダウンロードされました。読書はNパーセント完了しています"` /
`"本はダウンロードされていません"` (実測、Kindle 7.68)。
可視分しか AX に出ないので、ボタンに AXScrollDownByPage を perform して
スクロールしながら集める。
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from . import ax

logger = logging.getLogger(__name__)

# "巻" はシリーズ (複数巻をまとめた 1 ボタン)。漫画などが該当し、方針として対象外
_KNOWN_TAGS = frozenset(
    {"既読", "NEW", "PDF", "サンプル", "巻", "Prime Reading", "Kindle Unlimited"}
)
_PROGRESS_RE = re.compile(r"(\d+)パーセント")
_DOWNLOADED = "ダウンロードされました"
_NOT_DOWNLOADED = "本はダウンロードされていません"
_CLOSE_BOOK = "本を閉じる"
_CLOSE_SHEET = "閉じる"  # 書籍情報シート (サンプルを開くと出る) の閉じるボタン
_MAX_NAME_LEN = 80


@dataclass(frozen=True)
class Book:
    title: str
    author: str
    tags: tuple[str, ...]
    downloaded: bool
    progress_pct: int | None
    description: str  # AX の生文字列 (重複判定キー)

    @property
    def is_sample(self) -> bool:
        return "サンプル" in self.tags

    @property
    def is_pdf(self) -> bool:
        return "PDF" in self.tags

    @property
    def is_series(self) -> bool:
        return "巻" in self.tags


def parse_book(description: str, value: str | None) -> Book:
    """`"タイトル, 著者, タグ, "` + value → Book.

    末尾側から既知タグを剥がし、最初の ", " までをタイトル、残りを著者にする。
    欧米著者名は "Karp, Alexander C.; Zamiska, Nicholas W." のように ", " を含むが、
    日本語タイトルが ", " を含むことはまず無いのでこの切り方が最も外れにくい。"""
    parts = [p.strip() for p in description.split(", ")]
    while parts and parts[-1] == "":
        parts.pop()
    tags: list[str] = []
    while parts and parts[-1] in _KNOWN_TAGS:
        tags.insert(0, parts.pop())
    title = parts[0] if parts else ""
    author = ", ".join(parts[1:])
    v = value or ""
    m = _PROGRESS_RE.search(v)
    return Book(
        title=title,
        author=author,
        tags=tuple(tags),
        downloaded=_DOWNLOADED in v,
        progress_pct=int(m.group(1)) if m else None,
        description=description,
    )


def safe_name(title: str) -> str:
    """出力ディレクトリ名として使える 1 階層分の名前 (CaptureConfig.name の制約を満たす)."""
    name = title.replace("/", "／").replace("\x00", "").strip()
    name = name[:_MAX_NAME_LEN].rstrip()
    if name in ("", ".", ".."):
        name = "untitled"
    return name


def _is_book_button(desc: str) -> bool:
    return ", " in desc


def visible_books(app: ax.AXElement) -> list[ax.AXElement]:
    return ax.find(app, "AXButton", _is_book_button)


def scroll_to_top(app: ax.AXElement) -> None:
    prev: list[str] | None = None
    for _ in range(100):
        buttons = visible_books(app)
        names = [ax.description(b) for b in buttons]
        if not buttons or names == prev:
            return
        prev = names
        ax.perform(buttons[0], "AXScrollUpByPage")
        time.sleep(0.5)


def list_books(app: ax.AXElement) -> list[Book]:
    """ライブラリを上から下までスクロールして全書籍を集める (表示順)."""
    scroll_to_top(app)
    seen: dict[str, Book] = {}
    stale = 0
    for _ in range(500):
        buttons = visible_books(app)
        new = 0
        for b in buttons:
            desc = ax.description(b)
            if desc not in seen:
                seen[desc] = parse_book(desc, ax.value(b))
                new += 1
        if not buttons:
            break
        stale = 0 if new else stale + 1
        if stale >= 2:  # 2 回続けて新顔なし → 末尾
            break
        ax.perform(buttons[-1], "AXScrollDownByPage")
        time.sleep(0.5)
    logger.info("ライブラリ: %d 冊", len(seen))
    return list(seen.values())


def _same_book(desc: str, book: Book) -> bool:
    """description はダウンロード状態でタグが変わりうるので、タイトルと著者で突き合わせる."""
    other = parse_book(desc, None)
    return other.title == book.title and other.author == book.author


def _find_button(app: ax.AXElement, book: Book) -> ax.AXElement:
    """スクロールしながら目的の書籍ボタンを探す (可視分しか AX に出ないため)."""
    scroll_to_top(app)
    prev: list[str] | None = None
    for _ in range(500):
        buttons = visible_books(app)
        names = [ax.description(b) for b in buttons]
        for b, name in zip(buttons, names, strict=True):
            if _same_book(name, book):
                return b
        if not buttons or names == prev:
            break
        prev = names
        ax.perform(buttons[-1], "AXScrollDownByPage")
        time.sleep(0.5)
    raise LookupError(f"ライブラリに見つかりません: {book.title}")


def _visible_button(app: ax.AXElement, book: Book) -> ax.AXElement | None:
    """スクロールせずに、いま AX に出ているボタンから探す."""
    for b in visible_books(app):
        if _same_book(ax.description(b), book):
            return b
    return None


def _fully_inside_window(app: ax.AXElement, button: ax.AXElement) -> bool:
    win = ax.window_frame(app)
    f = ax.frame(button)
    if win is None or f is None:
        return True  # 判定できなければ押してみる
    wx, wy, ww, wh = win
    x, y, w, h = f
    return x >= wx and y >= wy and x + w <= wx + ww and y + h <= wy + wh


def _press_book(app: ax.AXElement, book: Book) -> ax.AXElement:
    """書籍ボタンを完全に画面内へ入れてから押す。画面端に半分だけ見えている
    ボタンは AX ツリーには出るが、押しても反応しない (実測)。
    `_find_button` はスクロール位置を先頭に戻すので、入れ直した後は可視分から探す。"""
    button = _find_button(app, book)
    for _ in range(3):
        logger.debug("button frame=%s window=%s", ax.frame(button), ax.window_frame(app))
        if _fully_inside_window(app, button):
            break
        ax.perform(button, "AXScrollToVisible")
        time.sleep(0.8)
        button = _visible_button(app, book) or button
    logger.debug("press: inside=%s", _fully_inside_window(app, button))
    ax.perform(button, "AXPress")
    return button


def in_reader(app: ax.AXElement) -> bool:
    """ライブラリの書籍ボタンが 1 つも無ければリーダー画面とみなす."""
    return not visible_books(app)


def open_book(
    app: ax.AXElement,
    book: Book,
    *,
    download_timeout: float = 600.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """書籍ボタンを押して開く。未ダウンロードなら 1 回目の押下で DL が始まるので、
    「ダウンロードされました」になるまで待ってもう一度押す。"""
    button = _find_button(app, book)
    ax.perform(button, "AXPress")
    if not book.downloaded:
        logger.info("ダウンロード待ち: %s", book.title)
        deadline = time.monotonic() + download_timeout
        while True:
            sleeper(3.0)
            button = _find_button(app, book)
            if _DOWNLOADED in (ax.value(button) or ""):
                break
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"ダウンロードが {download_timeout:.0f} 秒で終わりません: {book.title}"
                )
        ax.perform(button, "AXPress")
    deadline = time.monotonic() + 60.0
    while not in_reader(app):
        logger.debug("リーダー待ち: visible_books=%d", len(visible_books(app)))
        if time.monotonic() > deadline:
            raise TimeoutError(f"リーダーが開きません: {book.title}")
        sleeper(1.0)
    sleeper(3.0)  # 描画待ち
    dismiss_sheet(app)


def dismiss_sheet(app: ax.AXElement) -> bool:
    """リーダーに被さる書籍情報シート (「閉じる」「シェア」) があれば閉じる.

    サンプル本を開いたときに出る。出ている間は chrome (本を閉じる等) に届かない。"""
    buttons = ax.find(app, "AXButton", lambda d: d == _CLOSE_SHEET)
    if not buttons:
        return False
    logger.info("書籍情報シートを閉じます")
    ax.perform(buttons[0], "AXPress")
    time.sleep(1.0)
    return True


def close_book(app: ax.AXElement, *, geometry: tuple[int, int, int, int]) -> None:
    """chrome を出して「本を閉じる」を押し、ライブラリに戻る."""
    for _ in range(3):
        dismiss_sheet(app)
        ax.sweep_mouse(*geometry)
        buttons = ax.find(app, "AXButton", lambda d: d == _CLOSE_BOOK)
        if buttons:
            ax.perform(buttons[0], "AXPress")
            ax.park_mouse(*geometry)
            time.sleep(2.0)
            return
    if in_reader(app):
        raise RuntimeError("「本を閉じる」ボタンが見つかりません")
