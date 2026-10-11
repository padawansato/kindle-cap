"""BookSource から EPUB 3 (リフロー型・横書き) を組み立てる."""

from __future__ import annotations

import re

from ebooklib import epub

from book_epub.converter import Heading, extract_headings, md_to_xhtml_body, normalize_figure_srcs
from book_epub.loader import BookSource

# normalize_figure_srcs の出力は src を含む属性の順序を保証しないため、
# src の前後どちらに他の属性が来ても拾えるようにする。
_EPUB_IMG_RE = re.compile(r'<img\b[^>]*?src="figures/([^"]+)"[^>]*?/>')

_CSS = b"img { max-width: 100%; height: auto; }\n"


def build_epub(source: BookSource, author: str | None = None) -> tuple[epub.EpubBook, list[str]]:
    """EPUB を組み立ててオブジェクトと警告リストを返す。書き込みは呼び出し側。"""
    warnings: list[str] = []
    book = epub.EpubBook()
    book.set_identifier(f"kindle-cap-book-epub:{source.title}")
    book.set_title(source.title)
    book.set_language("ja")
    if author:
        book.add_author(author)

    if source.cover_png is not None:
        book.set_cover("cover.png", source.cover_png.read_bytes())

    css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=_CSS)
    book.add_item(css)

    available = _embed_figures(book, source)

    chapters: list[epub.EpubHtml] = []
    toc_entries: list[tuple[Heading, str]] = []
    for page in source.pages:
        file_name = f"page_{page.page_number:03d}.xhtml"
        html = normalize_figure_srcs(
            md_to_xhtml_body(page.markdown, title=source.title, drop_texts=page.running_heads)
        )
        html = _drop_missing_figures(html, available, warnings)
        marker = (
            f'<span epub:type="pagebreak" role="doc-pagebreak" id="page_{page.page_number:03d}"/>'
        )
        chapter = epub.EpubHtml(title=f"p.{page.page_number}", file_name=file_name, lang="ja")
        chapter.set_content(marker + html)
        chapter.add_item(css)
        book.add_item(chapter)
        chapters.append(chapter)
        toc_entries.extend((h, file_name) for h in extract_headings(page.markdown))

    toc = build_toc(toc_entries)
    if not toc:
        toc = [epub.Link(chapters[0].file_name, source.title, "start")]
    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]
    return book, warnings


def build_toc(entries: list[tuple[Heading, str]]) -> list[object]:
    """(見出し, href) の列から 2 階層の ebooklib toc 構造を作る純粋関数。

    level 1 を親、level 2-3 をその子にぶら下げる。親の無い level 2-3 は
    トップレベルに昇格させる。子が空の Section は単独 Link に落とす
    （ebooklib の nav 出力を安定させるため）。
    """
    toc: list[object] = []
    current_section: epub.Section | None = None
    current_children: list[epub.Link] | None = None
    for i, (heading, href) in enumerate(entries):
        link = epub.Link(href, heading.text, f"toc-{i}")
        if heading.level == 1:
            current_section = epub.Section(heading.text, href)
            current_children = []
            toc.append((current_section, current_children))
        elif current_children is not None:
            current_children.append(link)
        else:
            toc.append(link)

    result: list[object] = []
    for i, item in enumerate(toc):
        if isinstance(item, tuple):
            section, children = item
            if not children:
                result.append(epub.Link(section.href, section.title, f"sec-{i}"))
                continue
        result.append(item)
    return result


def _embed_figures(book: epub.EpubBook, source: BookSource) -> set[str]:
    """figures/ 配下の PNG を EPUB に埋め込み、利用可能ファイル名集合を返す。"""
    if source.figures_dir is None:
        return set()
    names: set[str] = set()
    for png in sorted(source.figures_dir.glob("*.png")):
        book.add_item(
            epub.EpubImage(
                uid=f"fig-{png.stem}",
                file_name=f"figures/{png.name}",
                media_type="image/png",
                content=png.read_bytes(),
            )
        )
        names.add(png.name)
    return names


def _drop_missing_figures(html: str, available: set[str], warnings: list[str]) -> str:
    """EPUB に存在しない図参照の img タグを除去し警告を積む。本文は維持する。"""

    def _sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in available:
            return m.group(0)
        warnings.append(f"図画像 {name} が figures/ に見つからないため img をスキップします")
        return ""

    return _EPUB_IMG_RE.sub(_sub, html)
