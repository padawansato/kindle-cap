"""book_ocr.cli のテスト (FakeEngine 注入で yomitoku 不要)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from book_ocr import cli
from book_ocr.models import BookMetadata, PageText


class FakeEngine:
    @property
    def name(self) -> str:
        return "fake"

    def run_batch(self, pngs: list[Path]) -> list[PageText]:
        return [
            PageText(
                page_number=int(p.stem.split("_")[-1]),
                png_path=p,
                markdown=f"OCR for {p.name}",
                ocr_engine=self.name,
            )
            for p in pngs
        ]


def _make_book_dir(tmp_path: Path, n_pages: int = 2) -> Path:
    book = tmp_path / "my-book"
    book.mkdir()
    for i in range(1, n_pages + 1):
        (book / f"page_{i:03d}.png").touch()
    return book


class TestRunInjectsFakeEngine:
    def test_run_writes_index_md_and_pages(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=2)
        meta = BookMetadata(
            title="my-book",
            page_count=2,
            captured_at=datetime(2026, 4, 28, tzinfo=UTC),
            ocr_engine="fake",
            output_dir=book,
        )
        pngs = sorted(book.glob("page_*.png"))

        cli._run(
            engine=FakeEngine(),
            meta=meta,
            png_paths=pngs,
            out_dir=book,
            book_md_filename="my-book.md",
        )

        assert (book / "index.json").exists()
        assert (book / "my-book.md").exists()
        assert (book / "pages" / "page_001.md").exists()
        assert (book / "pages" / "page_002.md").exists()

    def test_index_json_uses_meta_title(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=1)
        meta = BookMetadata(
            title="custom-title",
            page_count=1,
            captured_at=datetime(2026, 4, 28, tzinfo=UTC),
            ocr_engine="fake",
            output_dir=book,
        )
        pngs = sorted(book.glob("page_*.png"))

        cli._run(
            engine=FakeEngine(),
            meta=meta,
            png_paths=pngs,
            out_dir=book,
            book_md_filename="custom-title.md",
        )

        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        assert data["title"] == "custom-title"


class TestCliInvocation:
    """yomitoku を持たない unit 環境でも通るスモーク (失敗パスのみ)."""

    @pytest.fixture
    def app(self) -> typer.Typer:
        a = typer.Typer()
        a.command()(cli.ocr)
        return a

    def test_empty_dir_exits_with_error(self, tmp_path: Path, app: typer.Typer) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        runner = CliRunner()
        result = runner.invoke(app, [str(empty)])
        assert result.exit_code != 0
        assert "No page_*.png" in result.stdout or "No page_*.png" in (result.stderr or "")

    def test_missing_dir_exits_with_error(self, tmp_path: Path, app: typer.Typer) -> None:
        missing = tmp_path / "does-not-exist"
        runner = CliRunner()
        result = runner.invoke(app, [str(missing)])
        assert result.exit_code != 0
