"""book-epub CLI entry point."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import typer
from ebooklib import epub

from book_epub.builder import build_epub
from book_epub.loader import load_book, parse_page_spec
from book_epub.page_join import join_cross_page_sentences


def _sanitize_filename(name: str) -> str:
    """デフォルト出力ファイル名用にパス区切り文字を全角に置換する（--out 明示指定時は対象外）。"""
    return name.replace("/", "／").replace("\\", "＼")


def run_build_pipeline(
    book_dir: Path,
    title: str | None,
    author: str | None,
    out: Path | None,
    skip_pages: frozenset[int] = frozenset(),
    join_pages: bool = True,
) -> Path:
    """book_dir から EPUB を生成し、生成ファイルのパスを返す。警告は stderr へ。

    `join_pages` が真なら、ページ末尾で切れた文を次ページ先頭と連結してから組み立てる
    (EPUB 側だけの加工で、pages/*.md は変更しない)。
    """
    source, warnings = load_book(book_dir, title_override=title, skip_pages=skip_pages)
    if join_pages:
        source = dataclasses.replace(
            source, pages=join_cross_page_sentences(source.pages, title=source.title)
        )
    book, build_warnings = build_epub(source, author=author)
    for w in [*warnings, *build_warnings]:
        typer.echo(f"[警告] {w}", err=True)

    epub_path = out or (book_dir / f"{_sanitize_filename(source.title)}.epub")
    epub_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(epub_path), book)
    return epub_path


app = typer.Typer()


@app.command()
def build(
    book_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="book-ocr が出力した output/<book>/ ディレクトリ (pages/*.md を含む)",
    ),
    title: str | None = typer.Option(
        None, "--title", help="書名 (省略時は index.json の title、無ければディレクトリ名)"
    ),
    author: str | None = typer.Option(None, "--author", help="著者名 (EPUB メタデータ)"),
    out: Path | None = typer.Option(
        None, "--out", help="出力 EPUB パス (省略時は <book_dir>/<title>.epub)"
    ),
    skip_pages: str = typer.Option(
        "",
        "--skip-pages",
        help=(
            "EPUB に入れないページ番号 (例: 4-9,48)。原本の目次ページなど OCR ノイズが"
            "多く読み上げの邪魔になるページを外す (issue #68)"
        ),
    ),
    join_pages: bool = typer.Option(
        True,
        "--join-pages/--no-join-pages",
        help=(
            "ページ末尾で切れた文を次ページ先頭の段落と連結する (既定 on)。"
            "読み上げがページ境界で途切れないようにする"
        ),
    ),
) -> None:
    """book-ocr の成果物から読み上げ可能な図表入り EPUB 3 を生成する."""
    try:
        skip = parse_page_spec(skip_pages)
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--skip-pages") from e
    try:
        epub_path = run_build_pipeline(
            book_dir,
            title=title,
            author=author,
            out=out,
            skip_pages=skip,
            join_pages=join_pages,
        )
    except (FileNotFoundError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"EPUB complete: {epub_path}")


def run_build() -> None:
    app()
