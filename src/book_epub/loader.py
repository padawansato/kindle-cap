"""book-ocr 成果物 (book_dir) を読み込んで EPUB 組立の入力に変換する I/O 層."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# book_ocr.exporters.page_md の出力と対称: 先頭の "<!-- page:NNN -->\n\n" を剥がす
_PAGE_MARKER_RE = re.compile(r"^<!--\s*page:\d+\s*-->\s*\n+", re.DOTALL)


@dataclass(frozen=True)
class SourcePage:
    page_number: int
    markdown: str


@dataclass(frozen=True)
class BookSource:
    book_dir: Path
    title: str
    pages: list[SourcePage]
    figures_dir: Path | None
    cover_png: Path | None


def load_book(book_dir: Path, title_override: str | None = None) -> tuple[BookSource, list[str]]:
    """book_dir から pages md / title / figures / cover を読み込む。

    Returns:
        (BookSource, 警告メッセージのリスト)。致命的でない欠落は警告に落とす。
    Raises:
        FileNotFoundError: pages/ が無い、または page md が 1 枚も無い場合。
    """
    warnings: list[str] = []

    pages_dir = book_dir / "pages"
    if not pages_dir.is_dir():
        raise FileNotFoundError(
            f"{pages_dir} が見つかりません。先に book-ocr を実行してください: "
            f"uv run book-ocr {book_dir}/"
        )
    md_paths = sorted(pages_dir.glob("page_*.md"))
    if not md_paths:
        raise FileNotFoundError(
            f"{pages_dir} に page_*.md がありません。先に book-ocr を実行してください。"
        )

    pages = []
    for p in md_paths:
        try:
            page_number = int(p.stem.split("_")[-1])
        except ValueError:
            warnings.append(f"{p.name} はページ番号を認識できないためスキップします")
            continue
        pages.append(
            SourcePage(
                page_number=page_number,
                markdown=_PAGE_MARKER_RE.sub("", p.read_text(encoding="utf-8"), count=1),
            )
        )
    pages.sort(key=lambda page: page.page_number)

    title = title_override or _read_title(book_dir, warnings) or book_dir.name

    figures_dir: Path | None = book_dir / "figures"
    if figures_dir is not None and not figures_dir.is_dir():
        warnings.append(
            f"{figures_dir} がありません。テキストのみの EPUB を生成します"
            "（図表入りにするには book-ocr を --figure 付きで再実行してください）"
        )
        figures_dir = None

    cover_png: Path | None = book_dir / "page_001.png"
    if cover_png is not None and not cover_png.exists():
        cover_png = None

    return (
        BookSource(
            book_dir=book_dir,
            title=title,
            pages=pages,
            figures_dir=figures_dir,
            cover_png=cover_png,
        ),
        warnings,
    )


def _read_title(book_dir: Path, warnings: list[str]) -> str | None:
    index_path = book_dir / "index.json"
    if not index_path.exists():
        warnings.append(f"{index_path} がありません。ディレクトリ名をタイトルに使います")
        return None
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warnings.append(f"{index_path} を JSON として読めません。ディレクトリ名を使います")
        return None
    if not isinstance(data, dict):
        warnings.append(f"{index_path} の形式が不正です。ディレクトリ名を使います")
        return None
    title = data.get("title")
    return title if isinstance(title, str) and title else None
