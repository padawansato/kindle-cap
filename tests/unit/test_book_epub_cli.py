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
