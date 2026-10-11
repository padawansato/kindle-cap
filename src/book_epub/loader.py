"""book-ocr 成果物 (book_dir) を読み込んで EPUB 組立の入力に変換する I/O 層."""

from __future__ import annotations

import dataclasses
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from book_epub.converter import normalize_paragraph_text
from book_ocr.reading_order import page_image_size

# book_ocr.exporters.page_md の出力と対称: 先頭の "<!-- page:NNN -->\n\n" を剥がす
_PAGE_MARKER_RE = re.compile(r"^<!--\s*page:\d+\s*-->\s*\n+", re.DOTALL)


@dataclass(frozen=True)
class SourcePage:
    page_number: int
    markdown: str
    # このページで柱とみなす段落 (normalize_paragraph_text 済み)。converter が落とす (#109)
    running_heads: frozenset[str] = frozenset()


@dataclass(frozen=True)
class BookSource:
    book_dir: Path
    title: str
    pages: list[SourcePage]
    figures_dir: Path | None
    cover_png: Path | None


_PAGE_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")

# 柱 (#109) の検出: ページの天 (横書き段落) または小口 (縦書き段落) のこの幅の帯にある
# 短い段落が、この冊数以上のページで繰り返されたら柱とみなす。撮影済み 4 冊の計測で、
# 縦書き本の章名 (小口に縦書き、7 種 55 回) と横書き本の書名の柱・窓タイトルだけが該当し、
# 本文の誤検出はなかった
_MARGIN_BAND = 0.08
_RUNNING_HEAD_MIN_PAGES = 3
_RUNNING_HEAD_MAX_CHARS = 60


def parse_page_spec(spec: str) -> frozenset[int]:
    """`"4-9,48"` のようなページ指定を 1 始まりのページ番号集合にする (issue #68)。

    Raises:
        ValueError: 数字でない、0 以下、範囲が逆 (`5-2`) など。
    """
    pages: set[int] = set()
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        m = _PAGE_RANGE_RE.match(token)
        if m is None:
            raise ValueError(f"ページ指定を解釈できません: {token!r} (例: 4-9,48)")
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) is not None else start
        if start < 1 or end < start:
            raise ValueError(f"ページ指定が不正です: {token!r} (1 以上で、範囲は小さい順)")
        pages.update(range(start, end + 1))
    return frozenset(pages)


def load_book(
    book_dir: Path,
    title_override: str | None = None,
    skip_pages: frozenset[int] = frozenset(),
) -> tuple[BookSource, list[str]]:
    """book_dir から pages md / title / figures / cover を読み込む。

    `skip_pages` のページ番号は EPUB に入れない (原本の目次ページなど、OCR ノイズが
    多く読み上げの邪魔になるページを外す用。issue #68)。

    Returns:
        (BookSource, 警告メッセージのリスト)。致命的でない欠落は警告に落とす。
    Raises:
        FileNotFoundError: pages/ が無い、または page md が 1 枚も無い場合。
        ValueError: skip_pages で全ページを外してしまった場合。
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

    heads = _find_running_heads(book_dir, [page.page_number for page in pages], warnings)
    pages = [
        dataclasses.replace(page, running_heads=heads.get(page.page_number, frozenset()))
        for page in pages
    ]

    if skip_pages:
        present = {page.page_number for page in pages}
        missing = sorted(skip_pages - present)
        if missing:
            warnings.append(
                "--skip-pages に存在しないページがあります: " + ", ".join(str(n) for n in missing)
            )
        pages = [page for page in pages if page.page_number not in skip_pages]
        if not pages:
            raise ValueError("--skip-pages で全ページを外してしまいました")

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


def _find_running_heads(
    book_dir: Path, page_numbers: list[int], warnings: list[str]
) -> dict[int, frozenset[str]]:
    """pages/page_NNN.json の段落の位置から、ページごとの柱の文字列集合を返す (#109)。

    md には位置が無いので JSON の `box` を見る。ページ画像 (page_NNN.png) の大きさを基準に、
    天の帯にある横書き段落と小口の帯にある縦書き段落のうち短いものを候補にし、
    `_RUNNING_HEAD_MIN_PAGES` ページ以上で同じ文字列が出たものを柱とみなす。
    該当したページだけに記録するので、章の扉で本文として出る同じ文字列は残る。
    JSON が無いページは空集合。
    """
    candidates: dict[int, set[str]] = {}
    for n in page_numbers:
        json_path = book_dir / "pages" / f"page_{n:03d}.json"
        if not json_path.exists():
            continue
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            warnings.append(f"{json_path} を JSON として読めません。柱の検出から外します")
            continue
        paragraphs = raw.get("paragraphs", []) if isinstance(raw, dict) else []
        size = page_image_size(book_dir / f"page_{n:03d}.png") or _extent(paragraphs)
        if size is None:
            continue
        width, height = size
        found = set()
        for p in paragraphs:
            text = normalize_paragraph_text(str(p.get("contents", "")))
            if not text or len(text) > _RUNNING_HEAD_MAX_CHARS:
                continue
            x0, _y0, x1, y1 = p["box"]
            if p.get("direction") == "vertical":
                in_margin = x1 < width * _MARGIN_BAND or x0 > width * (1 - _MARGIN_BAND)
            else:
                in_margin = y1 < height * _MARGIN_BAND
            if in_margin:
                found.add(text)
        if found:
            candidates[n] = found

    pages_per_text = Counter(text for found in candidates.values() for text in found)
    repeated = {text for text, c in pages_per_text.items() if c >= _RUNNING_HEAD_MIN_PAGES}
    return {n: frozenset(found & repeated) for n, found in candidates.items() if found & repeated}


def _extent(paragraphs: list[dict[str, Any]]) -> tuple[int, int] | None:
    boxes = [p["box"] for p in paragraphs if "box" in p]
    if not boxes:
        return None
    return int(max(b[2] for b in boxes)), int(max(b[3] for b in boxes))


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
