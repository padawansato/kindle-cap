"""ページ末尾で切れた文を次ページ先頭と再結合する純粋関数 (副作用なし).

book-ocr はページ単位で markdown を出すため、ページをまたぐ文はページ N の最後の
段落とページ N+1 の最初の段落に割れる。EPUB の読み上げではここが最も目立つ
切れ目になるので、EPUB 組立の直前に連結する。pages/*.md (OCR の正準出力) は触らない。
"""

from __future__ import annotations

import dataclasses
import re

from book_epub.converter import is_dropped_paragraph
from book_epub.loader import SourcePage

_BLOCK_SEP_RE = re.compile(r"\n[ \t]*\n+")
# 段落でない行 (見出し・図・表・リスト)。ブロック内のどこかに 1 行でもあれば結合しない
_NON_PARAGRAPH_LINE_RE = re.compile(r"^(?:#|<img|<table|\||[-*] |\d+\. )")
# 数字と記号・空白だけのブロックはノンブル (ページ番号) とみなして結合しない
_NOMBRE_RE = re.compile(r"^[\d\s\-–—−ー・.,()（）]+$")
_TERMINATORS = frozenset("。．.！!？?」』）)】")
# 次ページ先頭がこれらで始まるなら新しい段落・箇条書き・会話の開始とみなす
_NEW_PARAGRAPH_STARTS = frozenset("　 ○●◎◇◆□■▶▷・※「『（(【［[〈《")


def join_cross_page_sentences(
    pages: list[SourcePage], title: str | None = None
) -> list[SourcePage]:
    """連続するページ N, N+1 の組ごとに、N の最後の段落と N+1 の最初の段落を連結する。

    EPUB 変換時に落とされるブロック (ノンブル・`title` と一致する柱・1 文字段落。
    `converter.is_dropped_paragraph`) は飛ばし、その内側の段落同士を境界とみなす。
    飛ばしたブロックはその場に残す (どのみち変換時に落ちる)。

    結合するのは、N の最後のブロックが終端記号で終わらない通常の段落で、N+1 の
    最初のブロックが字下げ・箇条書き記号・開き括弧で始まらない通常の段落のときだけ。
    page_number が連番でない組 (--skip-pages で間が抜けた) は結合しない。
    各組は 1 回だけ判定し、結合で空になったページも要素としては残す
    (ページ番号と pagebreak マーカーを保つため)。
    """
    blocks = [_split_blocks(p.markdown) for p in pages]
    changed = [False] * len(pages)
    for i in range(len(pages) - 1):
        if pages[i + 1].page_number != pages[i].page_number + 1:
            continue
        prev, nxt = blocks[i], blocks[i + 1]
        tail = _last_kept_index(prev, title)
        head = _first_kept_index(nxt, title)
        if tail is None or head is None or not _can_join(prev[tail], nxt[head]):
            continue
        prev[tail] = _concat(prev[tail], nxt.pop(head))
        changed[i] = changed[i + 1] = True

    return [
        dataclasses.replace(page, markdown="\n\n".join(b)) if dirty else page
        for page, b, dirty in zip(pages, blocks, changed, strict=True)
    ]


def _split_blocks(markdown: str) -> list[str]:
    return [b for b in _BLOCK_SEP_RE.split(markdown.strip("\n")) if b.strip()]


def _last_kept_index(blocks: list[str], title: str | None) -> int | None:
    for i in range(len(blocks) - 1, -1, -1):
        if not is_dropped_paragraph(blocks[i], title):
            return i
    return None


def _first_kept_index(blocks: list[str], title: str | None) -> int | None:
    for i, block in enumerate(blocks):
        if not is_dropped_paragraph(block, title):
            return i
    return None


def _is_plain_paragraph(block: str) -> bool:
    return not any(_NON_PARAGRAPH_LINE_RE.match(line.lstrip(" ")) for line in block.splitlines())


def _can_join(tail_block: str, head_block: str) -> bool:
    tail = tail_block.rstrip()
    if _NOMBRE_RE.match(tail) or _NOMBRE_RE.match(head_block):
        return False
    if not (_is_plain_paragraph(tail) and _is_plain_paragraph(head_block)):
        return False
    return tail[-1] not in _TERMINATORS and head_block[0] not in _NEW_PARAGRAPH_STARTS


def _concat(tail_block: str, head_block: str) -> str:
    tail = tail_block.rstrip()
    head = head_block.lstrip("\n")
    sep = " " if _is_ascii_alnum(tail[-1]) and _is_ascii_alnum(head[0]) else ""
    return tail + sep + head


def _is_ascii_alnum(ch: str) -> bool:
    return ch.isascii() and ch.isalnum()
