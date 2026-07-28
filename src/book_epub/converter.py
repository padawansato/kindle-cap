"""Markdown → XHTML 変換の純粋関数群（副作用なし）."""

from __future__ import annotations

import re
from dataclasses import dataclass

import markdown as md_lib

# <img src="figures/..."> / <img src="../figures/..."> を XHTML 自己終了タグに正規化
_FIGURE_IMG_RE = re.compile(r'<img src="(?:\.\./)?figures/([^"]+)"([^>]*?)/?>')
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)


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
        attrs = m.group(2).rstrip()
        return f'<img src="figures/{m.group(1)}"{attrs}/>'

    return _FIGURE_IMG_RE.sub(_sub, html)


def extract_headings(markdown_text: str) -> list[Heading]:
    """`#`〜`###` の見出しを出現順に返す（目次生成用）。"""
    return [Heading(len(m.group(1)), m.group(2)) for m in _HEADING_RE.finditer(markdown_text)]
