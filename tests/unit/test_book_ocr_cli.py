"""book_ocr.cli のテスト (FakeEngine 注入で yomitoku 不要)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from book_ocr import cli
from book_ocr.cli import run_ocr_pipeline
from book_ocr.models import PageText


class FakeEngine:
    @property
    def name(self) -> str:
        return "fake"

    @property
    def version(self) -> str:
        return "0.0.0-fake"

    @property
    def settings(self) -> dict[str, Any]:
        return {"engine": "fake"}

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


class TestRunOcrPipeline:
    def test_writes_index_md_and_pages(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=2)

        out_path = run_ocr_pipeline(book_dir=book, engine=FakeEngine())

        assert out_path == book / "my-book.md"
        assert (book / "index.json").exists()
        assert (book / "my-book.md").exists()
        assert (book / "pages" / "page_001.md").exists()
        assert (book / "pages" / "page_002.md").exists()

    def test_name_argument_overrides_book_dir_basename(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=1)

        out_path = run_ocr_pipeline(book_dir=book, name="custom-title", engine=FakeEngine())

        assert out_path == book / "custom-title.md"
        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        assert data["title"] == "custom-title"
        assert (book / "custom-title.md").exists()

    def test_out_argument_redirects_output_dir(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=1)
        elsewhere = tmp_path / "elsewhere"

        out_path = run_ocr_pipeline(book_dir=book, out=elsewhere, engine=FakeEngine())

        assert out_path == elsewhere / "my-book.md"
        assert (elsewhere / "index.json").exists()
        assert (elsewhere / "my-book.md").exists()

    def test_empty_dir_raises_file_not_found(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="No page_"):
            run_ocr_pipeline(book_dir=empty, engine=FakeEngine())


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


class TestChunkSizeOption:
    """--chunk-size CLI フラグが YomiTokuEngine に伝搬すること (issue #36)."""

    @patch("book_ocr.cli.YomiTokuEngine")
    def test_chunk_size_propagates_to_engine(
        self, mock_engine_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_engine = MagicMock()
        mock_engine.run_batch.return_value = []
        mock_engine.name = "yomitoku"
        mock_engine.version = "0.12.0"
        mock_engine.settings = {"device": "mps"}
        mock_engine_cls.return_value = mock_engine
        book = _make_book_dir(tmp_path, n_pages=1)

        run_ocr_pipeline(book_dir=book, chunk_size=50)

        kwargs = mock_engine_cls.call_args.kwargs
        assert kwargs["chunk_size"] == 50

    @patch("book_ocr.cli.YomiTokuEngine")
    def test_chunk_size_default_is_none(self, mock_engine_cls: MagicMock, tmp_path: Path) -> None:
        mock_engine = MagicMock()
        mock_engine.run_batch.return_value = []
        mock_engine.name = "yomitoku"
        mock_engine.version = "0.12.0"
        mock_engine.settings = {"device": "mps"}
        mock_engine_cls.return_value = mock_engine
        book = _make_book_dir(tmp_path, n_pages=1)

        run_ocr_pipeline(book_dir=book)

        kwargs = mock_engine_cls.call_args.kwargs
        assert kwargs["chunk_size"] is None

    def test_cli_chunk_size_flag_parses(self, tmp_path: Path) -> None:
        """--chunk-size N が CLI から typer.Option で受け取れること (smoke)."""
        empty = tmp_path / "empty"
        empty.mkdir()
        app = typer.Typer()
        app.command()(cli.ocr)
        runner = CliRunner()
        # 空 dir なので exit != 0 だが、--chunk-size 未知フラグエラーではないこと
        result = runner.invoke(app, [str(empty), "--chunk-size", "50"])
        assert result.exit_code != 0
        assert "No page_*.png" in result.stdout or "No page_*.png" in (result.stderr or "")


class TestTimeoutSecOption:
    """--timeout-sec CLI フラグが YomiTokuEngine に伝搬すること (issue #37)."""

    @patch("book_ocr.cli.YomiTokuEngine")
    def test_timeout_sec_propagates_to_engine(
        self, mock_engine_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_engine = MagicMock()
        mock_engine.run_batch.return_value = []
        mock_engine.name = "yomitoku"
        mock_engine.version = "0.12.0"
        mock_engine.settings = {"device": "mps"}
        mock_engine_cls.return_value = mock_engine
        book = _make_book_dir(tmp_path, n_pages=1)

        run_ocr_pipeline(book_dir=book, timeout_sec=7200.0)

        kwargs = mock_engine_cls.call_args.kwargs
        assert kwargs["timeout_sec"] == 7200.0

    @patch("book_ocr.cli.YomiTokuEngine")
    def test_timeout_sec_default_is_1800(self, mock_engine_cls: MagicMock, tmp_path: Path) -> None:
        mock_engine = MagicMock()
        mock_engine.run_batch.return_value = []
        mock_engine.name = "yomitoku"
        mock_engine.version = "0.12.0"
        mock_engine.settings = {"device": "mps"}
        mock_engine_cls.return_value = mock_engine
        book = _make_book_dir(tmp_path, n_pages=1)

        run_ocr_pipeline(book_dir=book)

        kwargs = mock_engine_cls.call_args.kwargs
        assert kwargs["timeout_sec"] == 1800.0

    def test_cli_timeout_sec_flag_parses(self, tmp_path: Path) -> None:
        """--timeout-sec N が CLI から typer.Option で受け取れること (smoke)。"""
        empty = tmp_path / "empty"
        empty.mkdir()
        app = typer.Typer()
        app.command()(cli.ocr)
        runner = CliRunner()
        result = runner.invoke(app, [str(empty), "--timeout-sec", "3600"])
        assert result.exit_code != 0
        assert "No page_*.png" in result.stdout or "No page_*.png" in (result.stderr or "")


class TestIndexMetadataExtension:
    """issue #40: index.json に reproducibility メタが書き込まれること。"""

    def test_index_json_contains_engine_version(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=1)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine())

        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        assert data["ocr_engine_version"] == "0.0.0-fake"

    def test_index_json_contains_ocr_settings(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=1)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine())

        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        assert data["ocr_settings"] == {"engine": "fake"}

    def test_index_json_contains_ocr_runtime_with_duration(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=1)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine())

        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        runtime = data["ocr_runtime"]
        assert "started_at" in runtime
        assert "finished_at" in runtime
        assert isinstance(runtime["duration_sec"], int | float)
        assert runtime["duration_sec"] >= 0

    def test_index_json_runtime_started_before_finished(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=1)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine())

        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        runtime = data["ocr_runtime"]
        assert runtime["started_at"] <= runtime["finished_at"]
