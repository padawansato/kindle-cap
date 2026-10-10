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
# 段落先頭は文字列先頭 (\A) か空行の直後に限る。MULTILINE の ^ だと段落途中の行頭にも当たり、
# 複数行段落の最終行が 1 文字だとその行だけ落ちていた (#107 の調査で判明)
_SINGLE_CHAR_PARAGRAPH_RE = re.compile(
    r"(?:(?<=\n\n)|\A)[^\s#<|\-*>][ \t]*(?:\n(?=\n|$)|\Z)", re.MULTILINE
)
# 空行で囲まれた「2〜4 桁の数字だけの段落」。ノンブル（ページ番号）や原本目次のページ番号で、
# 読み上げると本文の流れを切る。1 桁は _SINGLE_CHAR_PARAGRAPH_RE が拾う。5 桁以上は対象外
_PAGE_NUMBER_PARAGRAPH_RE = re.compile(
    r"(?:(?<=\n\n)|\A)[ \t]*[0-9０-９]{2,4}[ \t]*(?:\n(?=\n|$)|\Z)", re.MULTILINE
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


def _drop_page_number_paragraphs(text: str) -> str:
    """2〜4 桁の数字（半角・全角）だけの段落を落とす。見出し・表・リスト・HTML 行は数字だけにならないので対象外。"""
    return _PAGE_NUMBER_PARAGRAPH_RE.sub("", text)


def _drop_title_paragraphs(text: str, title: str | None) -> str:
    """書名と完全一致（前後空白を除く）する段落を落とす。ページ上端の柱が本文に混ざったもの。

    `# 書名` の見出しは一致しないので残る。
    """
    if title is None or not title.strip():
        return text
    pattern = re.compile(
        rf"(?:(?<=\n\n)|\A)[ \t]*{re.escape(title.strip())}[ \t]*(?:\n(?=\n|$)|\Z)", re.MULTILINE
    )
    return pattern.sub("", text)


def md_to_xhtml_body(markdown_text: str, title: str | None = None) -> str:
    """Markdown を HTML 本文（body 内側）に変換する。表の html は素通し。

    yomitoku 由来の行折り返し `<br>`（原本のレイアウト都合の強制改行）は
    リフロー表示を破綻させるため、変換前に除去する。装飾見出しが割れてできた
    1 文字だけの段落も落とす (issue #68)。読み上げの邪魔になるノンブル（2〜4 桁の
    数字だけの段落）と、`title` と一致する柱の段落も落とす。
    """
    text = _drop_noise_paragraphs(_strip_forced_linebreaks(markdown_text), title)
    return str(md_lib.markdown(text, extensions=["tables"]))


def _drop_noise_paragraphs(text: str, title: str | None) -> str:
    return _drop_title_paragraphs(
        _drop_page_number_paragraphs(_drop_single_char_paragraphs(text)), title
    )


def is_dropped_paragraph(block: str, title: str | None = None) -> bool:
    """空行区切りの 1 ブロックが md_to_xhtml_body で丸ごと落とされるかを返す。

    ページ間の文の再結合 (page_join) が、変換時に消えるノンブル・柱・1 文字段落を
    飛ばして実質の段落境界を探すのに使う。判定は md_to_xhtml_body と同じ処理で行う。
    """
    return not _drop_noise_paragraphs(_strip_forced_linebreaks(block) + "\n", title).strip()


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
