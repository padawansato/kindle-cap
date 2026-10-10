"""Markdown → XHTML 変換の純粋関数群（副作用なし）."""

from __future__ import annotations

import re
from dataclasses import dataclass

import markdown as md_lib

# <img ...src="figures/..."> / <img ...src="../figures/..."> を XHTML 自己終了タグに正規化（属性順序に依存しない）
_FIGURE_IMG_RE = re.compile(r'<img\b([^>]*?)src="(?:\.\./)?figures/([^"]+)"([^>]*?)/?>')
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
# 空行で囲まれた「1 文字だけの段落」。縦書きの装飾見出し (「解決法」) が yomitoku で
# 1 文字ずつの段落に割れたもの (issue #68)。本文で 1 文字だけの段落は正当には出ない
_SINGLE_CHAR_PARAGRAPH_RE = re.compile(r"(?:(?<=\n\n)|^)[^\s#<|\-*>][ \t]*\n(?=\n|$)", re.MULTILINE)
# 空行で囲まれた「数字だけ 2〜4 桁 (半角・全角)」の 1 行段落 = ノンブル (ページ番号)
_PAGE_NUMBER_PARAGRAPH_RE = re.compile(
    r"(?:(?<=\n\n)|^)[ \t]*[0-9０-９]{2,4}[ \t]*\n(?=\n|$)", re.MULTILINE
)


@dataclass(frozen=True)
class Heading:
    level: int
    text: str


def _strip_forced_linebreaks(text: str) -> str:
    """yomitoku が原本レイアウトの行折り返し位置に埋め込む `<br>` を除去する。

    前後が両方 ASCII 英数字なら単語結合を防ぐため半角スペースに置換し、
    それ以外（日本語の行折り返し）は空文字で連結する。
    """

    def _repl(m: re.Match[str]) -> str:
        start, end = m.span()
        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < len(text) else ""
        if before.isascii() and before.isalnum() and after.isascii() and after.isalnum():
            return " "
        return ""

    return _BR_TAG_RE.sub(_repl, text)


def _drop_single_char_paragraphs(text: str) -> str:
    """1 文字だけの段落を落とす (issue #68)。見出し・HTML・表・リスト行は対象外。"""
    return _SINGLE_CHAR_PARAGRAPH_RE.sub("", text)


def _drop_page_numbers(text: str) -> str:
    """ノンブル (数字だけ 2〜4 桁の段落) を落とす。読み上げで邪魔になるため。"""
    return _PAGE_NUMBER_PARAGRAPH_RE.sub("", text)


def _drop_running_head(text: str, title: str | None) -> str:
    """書名と完全一致 (前後空白除く) する 1 行段落 (柱) を落とす。`# 書名` 見出しは残す。"""
    if not title or not title.strip():
        return text
    pattern = re.compile(
        r"(?:(?<=\n\n)|^)[ \t]*" + re.escape(title.strip()) + r"[ \t]*\n(?=\n|$)", re.MULTILINE
    )
    return pattern.sub("", text)


def md_to_xhtml_body(markdown_text: str, title: str | None = None) -> str:
    """Markdown を HTML 本文（body 内側）に変換する。表の html は素通し。

    yomitoku 由来の行折り返し `<br>`（原本のレイアウト都合の強制改行）は
    リフロー表示を破綻させるため、変換前に除去する。装飾見出しが割れてできた
    1 文字だけの段落も落とす (issue #68)。読み上げの邪魔になるノンブルと、
    `title` と一致する柱も落とす。
    """
    text = _drop_single_char_paragraphs(_strip_forced_linebreaks(markdown_text))
    text = _drop_running_head(_drop_page_numbers(text), title)
    return str(md_lib.markdown(text, extensions=["tables"]))


def normalize_figure_srcs(html: str) -> str:
    """図参照を EPUB 内パス (figures/...) に正規化し、XHTML 自己終了タグにする。"""

    def _sub(m: re.Match[str]) -> str:
        before_attrs = m.group(1).strip()
        filename = m.group(2)
        after_attrs = m.group(3).strip()
        # src の前後の属性を保持して再構築
        parts = ["<img"]
        if before_attrs:
            parts.append(f" {before_attrs}")
        parts.append(f' src="figures/{filename}"')
        if after_attrs:
            parts.append(f" {after_attrs}")
        parts.append("/>")
        return "".join(parts)

    return _FIGURE_IMG_RE.sub(_sub, html)


def extract_headings(markdown_text: str) -> list[Heading]:
    """`#`〜`###` の見出しを出現順に返す（目次生成用）。

    yomitoku の md 見出しは行内改行を `<br>` として含むことがあるため、
    HTML タグは除去する。タグ除去後に空文字列になった見出しは結果から除外する。
    """
    headings = []
    for m in _HEADING_RE.finditer(markdown_text):
        text = _HTML_TAG_RE.sub("", m.group(2))
        if text:
            headings.append(Heading(len(m.group(1)), text))
    return headings
