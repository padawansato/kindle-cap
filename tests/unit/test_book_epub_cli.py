"""book_epub.cli の unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from book_epub.cli import app, run_build_pipeline

runner = CliRunner()


def _make_book_dir(tmp_path: Path) -> Path:
    book_dir = tmp_path / "my-book"
    pages = book_dir / "pages"
    pages.mkdir(parents=True)
    (pages / "page_001.md").write_text("<!-- page:001 -->\n\n# 第1章\n本文", encoding="utf-8")
    (book_dir / "index.json").write_text(json.dumps({"title": "統合本"}), encoding="utf-8")
    return book_dir


class TestRunBuildPipeline:
    def test_writes_epub_to_book_dir_by_default(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        out = run_build_pipeline(book_dir, title=None, author=None, out=None)
        assert out == book_dir / "統合本.epub"
        assert out.exists()

    def test_out_option_overrides_destination(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        dest = tmp_path / "elsewhere" / "custom.epub"
        out = run_build_pipeline(book_dir, title=None, author=None, out=dest)
        assert out == dest
        assert dest.exists()

    def test_missing_pages_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            run_build_pipeline(empty, title=None, author=None, out=None)

    def test_title_with_slash_is_sanitized_in_default_out_path(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        out = run_build_pipeline(book_dir, title="AI/ML入門", author=None, out=None)
        assert out.parent == book_dir
        assert out.name == "AI／ML入門.epub"
        assert out.exists()

    def test_explicit_out_option_is_not_sanitized(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        dest = tmp_path / "elsewhere" / "custom.epub"
        out = run_build_pipeline(book_dir, title="AI/ML入門", author=None, out=dest)
        assert out == dest
        assert out.exists()


class TestCliInvocation:
    def test_missing_pages_returns_exit_code_1(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        result = runner.invoke(app, [str(empty)])
        assert result.exit_code == 1
        assert "book-ocr" in result.stdout or "book-ocr" in result.stderr

    def test_valid_book_dir_returns_exit_code_0(self, tmp_path: Path) -> None:
        book_dir = _make_book_dir(tmp_path)
        result = runner.invoke(app, [str(book_dir)])
        assert result.exit_code == 0
        assert "EPUB complete:" in result.stdout


def test_cli_skip_pages_is_applied_and_invalid_spec_exits_nonzero(tmp_path: Path) -> None:
    book_dir = _make_book_dir(tmp_path)
    (book_dir / "pages" / "page_002.md").write_text(
        "<!-- page:002 -->\n\n目次 000", encoding="utf-8"
    )
    dest = tmp_path / "skip.epub"
    result = runner.invoke(app, [str(book_dir), "--skip-pages", "2", "--out", str(dest)])
    assert result.exit_code == 0, result.output
    assert dest.exists()
    from ebooklib import epub

    book = epub.read_epub(str(dest))
    bodies = [
        item.get_content().decode("utf-8")
        for item in book.get_items()
        if item.get_type() == 9  # ITEM_DOCUMENT
    ]
    assert not any("目次 000" in b for b in bodies)

    result = runner.invoke(app, [str(book_dir), "--skip-pages", "x"])
    assert result.exit_code != 0


def test_cli_joins_sentence_split_across_pages_unless_disabled(tmp_path: Path) -> None:
    from ebooklib import epub

    book_dir = _make_book_dir(tmp_path)
    pages = book_dir / "pages"
    (pages / "page_001.md").write_text(
        "<!-- page:001 -->\n\n# 第1章\n\nページ末尾で、切れ<br>た文の前", encoding="utf-8"
    )
    (pages / "page_002.md").write_text(
        "<!-- page:002 -->\n\n半はここに続く。\n\n次の段落。", encoding="utf-8"
    )

    def bodies(dest: Path) -> dict[str, str]:
        return {
            item.get_name(): item.get_content().decode("utf-8")
            for item in epub.read_epub(str(dest)).get_items()
            if item.get_type() == 9  # ITEM_DOCUMENT
        }

    joined = tmp_path / "joined.epub"
    result = runner.invoke(app, [str(book_dir), "--out", str(joined)])
    assert result.exit_code == 0, result.output
    docs = bodies(joined)
    assert "<p>ページ末尾で、切れた文の前半はここに続く。</p>" in docs["page_001.xhtml"]
    assert "半はここに続く" not in docs["page_002.xhtml"]
    assert "<p>次の段落。</p>" in docs["page_002.xhtml"]
    # pages/*.md (OCR の正準出力) は書き換えない
    assert "半はここに続く。" in (pages / "page_002.md").read_text(encoding="utf-8")

    separate = tmp_path / "separate.epub"
    result = runner.invoke(app, [str(book_dir), "--no-join-pages", "--out", str(separate)])
    assert result.exit_code == 0, result.output
    docs = bodies(separate)
    assert "<p>ページ末尾で、切れた文の前</p>" in docs["page_001.xhtml"]
    assert "<p>半はここに続く。</p>" in docs["page_002.xhtml"]


def test_cli_drops_chapter_running_heads_found_by_json_boxes_and_joins_across_them(
    tmp_path: Path,
) -> None:
    """#109: 縦書き本の章名の柱 (小口の縦書き段落) は書名と一致しないので文字列では落とせない。
    pages/*.json の box で見つけて落とし、ページ間の文の再結合も柱を飛ばして行う"""
    from ebooklib import epub

    book_dir = _make_book_dir(tmp_path)
    pages = book_dir / "pages"
    head_md = "第1章 「睡眠の悩み」を何とかしたい\\!"
    head_json = "第1章 「睡眠の悩み」を何とかしたい!"
    mds = {
        1: "# 第1章\n\nページ末尾で、切れ<br>た文の前\n\n" + head_md,
        2: head_md + "\n\n半はここに続く。\n\n次の段落。",
        3: head_md + "\n\n三ページ目。",
    }
    png_header = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + (2940).to_bytes(4, "big")
        + (1846).to_bytes(4, "big")
    )
    for n, md in mds.items():
        (pages / f"page_{n:03d}.md").write_text(f"<!-- page:{n:03d} -->\n\n{md}", encoding="utf-8")
        (book_dir / f"page_{n:03d}.png").write_bytes(png_header)
        (pages / f"page_{n:03d}.json").write_text(
            json.dumps(
                {
                    "paragraphs": [
                        {
                            "box": [138, 200, 168, 640],
                            "contents": head_json,
                            "direction": "vertical",
                            "order": 0,
                            "role": None,
                        }
                    ],
                    "tables": [],
                    "figures": [],
                    "words": [],
                }
            ),
            encoding="utf-8",
        )

    dest = tmp_path / "out.epub"
    result = runner.invoke(app, [str(book_dir), "--out", str(dest)])
    assert result.exit_code == 0, result.output
    docs = {
        item.get_name(): item.get_content().decode("utf-8")
        for item in epub.read_epub(str(dest)).get_items()
        if item.get_type() == 9  # ITEM_DOCUMENT
    }
    assert "<p>ページ末尾で、切れた文の前半はここに続く。</p>" in docs["page_001.xhtml"]
    for name in ("page_001.xhtml", "page_002.xhtml", "page_003.xhtml"):
        assert "睡眠の悩み" not in docs[name], name
    assert (
        "<p>次の段落。</p>" in docs["page_002.xhtml"] and "三ページ目。" in docs["page_003.xhtml"]
    )
