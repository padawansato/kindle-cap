"""book_epub.loader の unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from book_epub.loader import load_book


def _make_book_dir(tmp_path: Path, *, with_index: bool = True, with_figures: bool = True) -> Path:
    book_dir = tmp_path / "my-book"
    pages = book_dir / "pages"
    pages.mkdir(parents=True)
    (pages / "page_001.md").write_text("<!-- page:001 -->\n\n# 第1章\n本文1", encoding="utf-8")
    (pages / "page_002.md").write_text(
        '<!-- page:002 -->\n\n<img src="../figures/page_002_figure_0.png" alt="図">\n図中の文',
        encoding="utf-8",
    )
    if with_index:
        (book_dir / "index.json").write_text(json.dumps({"title": "実タイトル"}), encoding="utf-8")
    if with_figures:
        figs = book_dir / "figures"
        figs.mkdir()
        (figs / "page_002_figure_0.png").write_bytes(b"png")
    (book_dir / "page_001.png").write_bytes(b"cover")
    return book_dir


class TestLoadBook:
    def test_loads_pages_sorted_with_marker_stripped(self, tmp_path: Path) -> None:
        source, warnings = load_book(_make_book_dir(tmp_path))
        assert [p.page_number for p in source.pages] == [1, 2]
        assert source.pages[0].markdown.startswith("# 第1章")
        assert warnings == []

    def test_title_priority_override_then_index(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        assert load_book(book_dir)[0].title == "実タイトル"
        assert load_book(book_dir, title_override="上書き")[0].title == "上書き"

    def test_title_falls_back_to_dirname_with_warning(self, tmp_path: Path) -> None:
        source, warnings = load_book(_make_book_dir(tmp_path, with_index=False))
        assert source.title == "my-book"
        assert any("index.json" in w for w in warnings)

    def test_missing_figures_dir_warns(self, tmp_path: Path) -> None:
        source, warnings = load_book(_make_book_dir(tmp_path, with_figures=False))
        assert source.figures_dir is None
        assert any("figures" in w for w in warnings)

    def test_missing_pages_dir_raises_with_guidance(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="book-ocr"):
            load_book(empty)

    def test_cover_png_detected(self, tmp_path: Path) -> None:
        source, _ = load_book(_make_book_dir(tmp_path))
        assert source.cover_png is not None
        assert source.cover_png.name == "page_001.png"

    def test_index_json_malformed_not_dict_warns(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        (book_dir / "index.json").write_text("null", encoding="utf-8")
        source, warnings = load_book(book_dir)
        assert source.title == "my-book"
        assert any("形式が不正" in w for w in warnings)

    def test_pages_are_sorted_numerically_beyond_1000(self, tmp_path: Path) -> None:
        book_dir = tmp_path / "big-book"
        pages = book_dir / "pages"
        pages.mkdir(parents=True)
        for n in (999, 1000, 1001, 101):
            (pages / f"page_{n:03d}.md").write_text(
                f"<!-- page:{n:03d} -->\n\n本文{n}", encoding="utf-8"
            )
        source, _ = load_book(book_dir)
        assert [p.page_number for p in source.pages] == [101, 999, 1000, 1001]

    def test_non_numeric_stem_is_skipped_with_warning(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        (book_dir / "pages" / "page_backup.md").write_text("バックアップ", encoding="utf-8")
        source, warnings = load_book(book_dir)
        assert [p.page_number for p in source.pages] == [1, 2]
        assert any("page_backup.md" in w for w in warnings)


# ---------------------------------------------------------------------------
# --skip-pages (issue #68): 原本の目次ページなど OCR ノイズの多いページを EPUB から外す
# ---------------------------------------------------------------------------


class TestSkipPages:
    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ("2", {2}),
            ("4-6,9", {4, 5, 6, 9}),
            (" 1 , 3-3 ", {1, 3}),
            ("", set()),
        ],
    )
    def test_parse_page_spec(self, spec: str, expected: set[int]) -> None:
        from book_epub.loader import parse_page_spec

        assert parse_page_spec(spec) == frozenset(expected)

    @pytest.mark.parametrize("bad", ["0", "a", "5-2", "1-", "-3"])
    def test_parse_page_spec_rejects_invalid(self, bad: str) -> None:
        from book_epub.loader import parse_page_spec

        with pytest.raises(ValueError):
            parse_page_spec(bad)

    def test_skipped_pages_are_dropped_and_missing_ones_warn(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        source, warnings = load_book(book_dir, skip_pages=frozenset({2, 7}))
        assert [p.page_number for p in source.pages] == [1]
        assert any("7" in w for w in warnings)  # 存在しないページ指定は警告

    def test_skipping_every_page_raises(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        with pytest.raises(ValueError):
            load_book(book_dir, skip_pages=frozenset({1, 2}))


def _png_header(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
    )


def _paragraph(text: str, box: list[int], direction: str) -> dict[str, object]:
    return {"box": box, "contents": text, "direction": direction, "order": 0, "role": None}


class TestRunningHeads:
    def test_margin_paragraphs_repeated_on_three_pages_become_running_heads(
        self, tmp_path: Path
    ) -> None:
        """柱 (#109) は md に位置が無いので pages/*.json の box で見つける。実書籍の構造:
        縦書き本の章名の柱は小口 (左右 8% の帯) に縦書き、横書き本の柱と Kindle の窓タイトルは
        天 (上 8% の帯)。帯の中の短い段落が 3 ページ以上で繰り返されたら、そのページの
        柱として記録する。2 ページだけのもの、帯の外で繰り返す本文、JSON の無いページは対象外"""
        book_dir = tmp_path / "book"
        pages = book_dir / "pages"
        pages.mkdir(parents=True)
        chapter = "第1章 「睡眠の悩み」を何とかしたい!"
        for n in (1, 2, 3, 4):
            (pages / f"page_{n:03d}.md").write_text(
                f"<!-- page:{n:03d} -->\n\n本文{n}", encoding="utf-8"
            )
            if n == 4:
                continue  # JSON が無いページ
            (book_dir / f"page_{n:03d}.png").write_bytes(_png_header(2940, 1846))
            paragraphs = [
                _paragraph(chapter, [138, 200, 168, 640], "vertical"),  # 小口 (x < 8%)
                _paragraph("対策", [1800, 900, 1900, 960], "horizontal"),  # 帯の外で繰り返す
                _paragraph(f"本文{n}。", [400, 400, 1400, 900], "horizontal"),
            ]
            if n <= 2:
                paragraphs.append(
                    _paragraph("Kindle", [1422, 13, 1510, 38], "horizontal")
                )  # 2 ページだけ
            (pages / f"page_{n:03d}.json").write_text(
                json.dumps({"paragraphs": paragraphs, "tables": [], "figures": [], "words": []}),
                encoding="utf-8",
            )
        source, _ = load_book(book_dir)
        heads = [p.running_heads for p in source.pages]
        assert heads == [frozenset({"第1章「睡眠の悩み」を何とかしたい!"})] * 3 + [frozenset()]
