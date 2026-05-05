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


class TestPageRangeOption:
    """issue #39: --start-page / --end-page で範囲指定。"""

    def test_start_page_skips_earlier_pages(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=5)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), start_page=3)

        # page_003 〜 page_005 のみが OCR される
        assert (book / "pages" / "page_003.md").exists()
        assert (book / "pages" / "page_004.md").exists()
        assert (book / "pages" / "page_005.md").exists()
        assert not (book / "pages" / "page_001.md").exists()
        assert not (book / "pages" / "page_002.md").exists()

    def test_end_page_truncates_to_upper_bound(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=5)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), end_page=2)

        assert (book / "pages" / "page_001.md").exists()
        assert (book / "pages" / "page_002.md").exists()
        assert not (book / "pages" / "page_003.md").exists()

    def test_both_start_and_end_pages(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=5)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), start_page=2, end_page=4)

        assert not (book / "pages" / "page_001.md").exists()
        assert (book / "pages" / "page_002.md").exists()
        assert (book / "pages" / "page_003.md").exists()
        assert (book / "pages" / "page_004.md").exists()
        assert not (book / "pages" / "page_005.md").exists()

    def test_start_page_inclusive(self, tmp_path: Path) -> None:
        """start_page=N を指定すると、ちょうど page_N が含まれる (inclusive)。"""
        book = _make_book_dir(tmp_path, n_pages=3)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), start_page=2)

        assert (book / "pages" / "page_002.md").exists()
        assert (book / "pages" / "page_003.md").exists()

    def test_end_page_inclusive(self, tmp_path: Path) -> None:
        """end_page=N を指定すると、page_N も含まれる (inclusive)。"""
        book = _make_book_dir(tmp_path, n_pages=3)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), end_page=2)

        assert (book / "pages" / "page_002.md").exists()
        assert not (book / "pages" / "page_003.md").exists()

    def test_start_page_zero_rejected(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=3)
        with pytest.raises(ValueError, match="start_page"):
            run_ocr_pipeline(book_dir=book, engine=FakeEngine(), start_page=0)

    def test_start_page_greater_than_end_page_rejected(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=5)
        with pytest.raises(ValueError, match=r"end_page.*>=.*start_page"):
            run_ocr_pipeline(book_dir=book, engine=FakeEngine(), start_page=4, end_page=2)

    def test_range_with_no_pages_in_dir_raises(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=3)
        with pytest.raises(FileNotFoundError, match="No page_"):
            run_ocr_pipeline(book_dir=book, engine=FakeEngine(), start_page=10)

    def test_index_page_count_reflects_range(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=5)
        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), start_page=2, end_page=4)

        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        assert data["page_count"] == 3  # 2,3,4 の 3 ページ

    def test_cli_start_end_page_flags_parse(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        app = typer.Typer()
        app.command()(cli.ocr)
        runner = CliRunner()
        result = runner.invoke(app, [str(empty), "--start-page", "5", "--end-page", "10"])
        assert result.exit_code != 0  # No page_*.png なのでエラー終了
        assert "No page_*.png" in result.stdout or "No page_*.png" in (result.stderr or "")


class TestSkipExistingOption:
    """issue #41: --skip-existing で既存 page_NNN.md があるページは OCR をスキップ。"""

    def _seed_existing_page(self, book: Path, n: int, body: str) -> None:
        """`book/pages/page_NNN.md` に render_page_md と同じフォーマットで書き込む。"""
        pages_dir = book / "pages"
        pages_dir.mkdir(exist_ok=True)
        (pages_dir / f"page_{n:03d}.md").write_text(
            f"<!-- page:{n:03d} -->\n\n{body}", encoding="utf-8"
        )

    def test_default_skip_existing_is_false(self, tmp_path: Path) -> None:
        """default では既存 md があっても全ページ OCR する。"""
        book = _make_book_dir(tmp_path, n_pages=3)
        self._seed_existing_page(book, 1, "old content for page 1")

        # FakeEngine が呼び出された pngs を記録
        seen: list[Path] = []

        class CapturingEngine(FakeEngine):
            def run_batch(self, pngs: list[Path]) -> list[PageText]:
                seen.extend(pngs)
                return super().run_batch(pngs)

        run_ocr_pipeline(book_dir=book, engine=CapturingEngine())
        assert len(seen) == 3  # 既存があっても 3 枚すべて OCR

    def test_skip_existing_skips_pages_with_existing_md(self, tmp_path: Path) -> None:
        """既存 page_001.md があれば page_001 は OCR されない。"""
        book = _make_book_dir(tmp_path, n_pages=3)
        self._seed_existing_page(book, 1, "old content for page 1")

        seen: list[Path] = []

        class CapturingEngine(FakeEngine):
            def run_batch(self, pngs: list[Path]) -> list[PageText]:
                seen.extend(pngs)
                return super().run_batch(pngs)

        run_ocr_pipeline(book_dir=book, engine=CapturingEngine(), skip_existing=True)
        # page_002, page_003 のみ OCR
        assert sorted(p.name for p in seen) == ["page_002.png", "page_003.png"]

    def test_skip_existing_preserves_old_content_in_book_md(self, tmp_path: Path) -> None:
        """skip された既存ページは markdown 本体が保持され、book_md に含まれる。"""
        book = _make_book_dir(tmp_path, n_pages=2)
        self._seed_existing_page(book, 1, "OLD CONTENT FOR PAGE 1")

        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), skip_existing=True)

        book_md = (book / "my-book.md").read_text(encoding="utf-8")
        assert "OLD CONTENT FOR PAGE 1" in book_md  # 既存 page 1 は保持
        assert "OCR for page_002.png" in book_md  # 新規 page 2 は OCR

    def test_skip_existing_with_no_existing_runs_all(self, tmp_path: Path) -> None:
        book = _make_book_dir(tmp_path, n_pages=2)
        # 既存 md なし

        seen: list[Path] = []

        class CapturingEngine(FakeEngine):
            def run_batch(self, pngs: list[Path]) -> list[PageText]:
                seen.extend(pngs)
                return super().run_batch(pngs)

        run_ocr_pipeline(book_dir=book, engine=CapturingEngine(), skip_existing=True)
        assert len(seen) == 2

    def test_skip_existing_all_pages_existing_no_engine_call(self, tmp_path: Path) -> None:
        """全ページの md がすでにあれば engine は呼ばれない (高速化)。"""
        book = _make_book_dir(tmp_path, n_pages=2)
        self._seed_existing_page(book, 1, "p1")
        self._seed_existing_page(book, 2, "p2")

        engine_call_count = 0

        class CountingEngine(FakeEngine):
            def run_batch(self, pngs: list[Path]) -> list[PageText]:
                nonlocal engine_call_count
                engine_call_count += 1
                return super().run_batch(pngs)

        run_ocr_pipeline(book_dir=book, engine=CountingEngine(), skip_existing=True)
        assert engine_call_count == 0

    def test_skip_existing_empty_md_treated_as_missing(self, tmp_path: Path) -> None:
        """既存 md が空ファイルなら再 OCR する (壊れた状態のフォールバック)。"""
        book = _make_book_dir(tmp_path, n_pages=2)
        pages_dir = book / "pages"
        pages_dir.mkdir()
        (pages_dir / "page_001.md").write_text("", encoding="utf-8")

        seen: list[Path] = []

        class CapturingEngine(FakeEngine):
            def run_batch(self, pngs: list[Path]) -> list[PageText]:
                seen.extend(pngs)
                return super().run_batch(pngs)

        run_ocr_pipeline(book_dir=book, engine=CapturingEngine(), skip_existing=True)
        # 空ファイル page_001 も再 OCR、page_002 も新規 OCR
        assert len(seen) == 2

    def test_index_page_count_includes_skipped(self, tmp_path: Path) -> None:
        """skipped ページも index.json の page_count に含まれる。"""
        book = _make_book_dir(tmp_path, n_pages=3)
        self._seed_existing_page(book, 1, "p1")

        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), skip_existing=True)

        data = json.loads((book / "index.json").read_text(encoding="utf-8"))
        assert data["page_count"] == 3

    def test_cli_skip_existing_flag_parses(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        app = typer.Typer()
        app.command()(cli.ocr)
        runner = CliRunner()
        result = runner.invoke(app, [str(empty), "--skip-existing"])
        assert result.exit_code != 0
        assert "No page_*.png" in result.stdout or "No page_*.png" in (result.stderr or "")


class TestProgressOption:
    """issue #38: --progress / --no-progress が YomiTokuEngine に伝搬する。"""

    @patch("book_ocr.cli.YomiTokuEngine")
    def test_progress_default_is_true(self, mock_engine_cls: MagicMock, tmp_path: Path) -> None:
        mock_engine = MagicMock()
        mock_engine.run_batch.return_value = []
        mock_engine.name = "yomitoku"
        mock_engine.version = "0.12.0"
        mock_engine.settings = {"device": "mps"}
        mock_engine_cls.return_value = mock_engine
        book = _make_book_dir(tmp_path, n_pages=1)

        run_ocr_pipeline(book_dir=book)

        kwargs = mock_engine_cls.call_args.kwargs
        assert kwargs["progress"] is True

    @patch("book_ocr.cli.YomiTokuEngine")
    def test_progress_false_propagates(self, mock_engine_cls: MagicMock, tmp_path: Path) -> None:
        mock_engine = MagicMock()
        mock_engine.run_batch.return_value = []
        mock_engine.name = "yomitoku"
        mock_engine.version = "0.12.0"
        mock_engine.settings = {"device": "mps"}
        mock_engine_cls.return_value = mock_engine
        book = _make_book_dir(tmp_path, n_pages=1)

        run_ocr_pipeline(book_dir=book, progress=False)

        kwargs = mock_engine_cls.call_args.kwargs
        assert kwargs["progress"] is False

    def test_cli_no_progress_flag_parses(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        app = typer.Typer()
        app.command()(cli.ocr)
        runner = CliRunner()
        result = runner.invoke(app, [str(empty), "--no-progress"])
        assert result.exit_code != 0  # No page_*.png でエラー終了
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
