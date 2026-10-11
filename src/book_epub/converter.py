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
# Kindle の窓まわりが切り出しに入ったもの: 窓タイトル「Kindle」と読書進捗「15%」 (#109)。
# 背面撮影した 2 冊の計測で 256 枚中 86 枚 / 205 枚中 28 枚のページ先頭に「Kindle」が出ていた
_KINDLE_CHROME_PARAGRAPH_RE = re.compile(
    r"(?:(?<=\n\n)|\A)[ \t]*(?:Kindle|[0-9０-９]{1,3}[%％])[ \t]*(?:\n(?=\n|$)|\Z)", re.MULTILINE
)
# 柱 (書名 + 副題) の 1 行段落が書名の後に続けてよい最大文字数。副題はこれより短く、
# 書名で始まる本文はこれより長いか句点で終わる
_RUNNING_HEAD_MAX_TAIL = 80
# 空行区切り (段落境界)
_BLOCK_SEP_RE = re.compile(r"\n[ \t]*\n")
# 段落でないブロックの先頭文字 (見出し・HTML・表・リスト・引用)。drop_texts で落とす対象から外す
_NON_PARAGRAPH_START = "#<|-*>"
_BACKSLASH_OR_SPACE_RE = re.compile(r"[\\\s]+")


def normalize_paragraph_text(text: str) -> str:
    """段落の突き合わせ用の正規化: `<br>`・md のエスケープ (`\\`)・空白をすべて除く。

    yomitoku の JSON (`contents`) と md の段落は、空白の有無・`<br>`・`\\!` などの
    エスケープで食い違うので、両方をこれで揃えて比較する。
    """
    return _BACKSLASH_OR_SPACE_RE.sub("", _BR_TAG_RE.sub("", text))


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
    """書名で始まる柱の 1 行段落を落とす。ページ上端の柱が本文に混ざったもの (#109)。

    書名と完全一致するものに加え、書名の後に副題が続くもの
    (「コードレビューの教科書––なんとなく承認から抜け出すための観点と判断基準」) も落とす。
    句点・感嘆符・疑問符を含む段落と、書名の後が `_RUNNING_HEAD_MAX_TAIL` 文字を超える
    段落は本文とみなして残す。`# 書名` の見出しは一致しないので残る。
    """
    if title is None or not title.strip():
        return text
    pattern = re.compile(
        rf"(?:(?<=\n\n)|\A)[ \t]*{re.escape(title.strip())}[^\n。！？!?]{{0,{_RUNNING_HEAD_MAX_TAIL}}}"
        rf"(?:\n(?=\n|$)|\Z)",
        re.MULTILINE,
    )
    return pattern.sub("", text)


def _drop_kindle_chrome_paragraphs(text: str) -> str:
    """Kindle の窓タイトル「Kindle」と読書進捗「15%」だけの段落を落とす。"""
    return _KINDLE_CHROME_PARAGRAPH_RE.sub("", text)


def md_to_xhtml_body(
    markdown_text: str, title: str | None = None, drop_texts: frozenset[str] = frozenset()
) -> str:
    """Markdown を HTML 本文（body 内側）に変換する。表の html は素通し。

    yomitoku 由来の行折り返し `<br>`（原本のレイアウト都合の強制改行）は
    リフロー表示を破綻させるため、変換前に除去する。装飾見出しが割れてできた
    1 文字だけの段落も落とす (issue #68)。読み上げの邪魔になるノンブル（2〜4 桁の
    数字だけの段落）、Kindle の窓タイトル・進捗の段落、`title` で始まる柱の段落も落とす (#109)。
    `drop_texts` は loader が JSON の位置から見つけた柱 (章名など) の正規化済み文字列
    (`normalize_paragraph_text`) で、一致する段落を落とす。見出し・表・リスト行は対象外。
    """
    text = _drop_noise_paragraphs(_strip_forced_linebreaks(markdown_text), title, drop_texts)
    return str(md_lib.markdown(text, extensions=["tables"]))


def _drop_listed_paragraphs(text: str, drop_texts: frozenset[str]) -> str:
    """正規化した文字列が `drop_texts` にある段落ブロックを落とす (#109 の章名の柱)。"""
    if not drop_texts:
        return text
    kept = [
        block
        for block in _BLOCK_SEP_RE.split(text)
        if not block.strip()
        or block.lstrip()[0] in _NON_PARAGRAPH_START
        or normalize_paragraph_text(block) not in drop_texts
    ]
    return "\n\n".join(kept)


def _drop_noise_paragraphs(
    text: str, title: str | None, drop_texts: frozenset[str] = frozenset()
) -> str:
    # 先頭の段落を落とすと残りが "\n" で始まり、次の規則の「空行の直後」(\n\n) 判定が
    # 外れるので、規則ごとに先頭の改行を剥がす
    text = _drop_listed_paragraphs(text, drop_texts).lstrip("\n")
    text = _drop_single_char_paragraphs(text).lstrip("\n")
    text = _drop_page_number_paragraphs(text).lstrip("\n")
    text = _drop_kindle_chrome_paragraphs(text).lstrip("\n")
    return _drop_title_paragraphs(text, title)


def is_dropped_paragraph(
    block: str, title: str | None = None, drop_texts: frozenset[str] = frozenset()
) -> bool:
    """空行区切りの 1 ブロックが md_to_xhtml_body で丸ごと落とされるかを返す。

    ページ間の文の再結合 (page_join) が、変換時に消えるノンブル・柱・1 文字段落を
    飛ばして実質の段落境界を探すのに使う。判定は md_to_xhtml_body と同じ処理で行う。
    """
    return not _drop_noise_paragraphs(
        _strip_forced_linebreaks(block) + "\n", title, drop_texts
    ).strip()


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
