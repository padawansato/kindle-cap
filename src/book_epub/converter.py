"""Markdown → XHTML 変換の純粋関数群（副作用なし）."""

from __future__ import annotations

import re
from dataclasses import dataclass

import markdown as md_lib

# <img ...src="figures/..."> / <img ...src="../figures/..."> を XHTML 自己終了タグに正規化（属性順序に依存しない）
_FIGURE_IMG_RE = re.compile(r'<img\b([^>]*?)src="(?:\.\./)?figures/([^"]+)"([^>]*?)/?>')
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Heading:
    level: int
    text: str


def md_to_xhtml_body(markdown_text: str) -> str:
    """Markdown を HTML 本文（body 内側）に変換する。表の html は素通し。"""
    return str(md_lib.markdown(markdown_text, extensions=["tables"]))


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
    HTML タグは除去する（本文側の `<br>` は改行として有効なため対象外）。
    タグ除去後に空文字列になった見出しは結果から除外する。
    """
    headings = []
    for m in _HEADING_RE.finditer(markdown_text):
        text = _HTML_TAG_RE.sub("", m.group(2))
        if text:
            headings.append(Heading(len(m.group(1)), text))
    return headings
