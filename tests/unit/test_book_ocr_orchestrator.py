"""book_ocr.orchestrator のテスト (FakeEngine 注入で副作用なしを検証)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from book_ocr import orchestrator
from book_ocr.models import BookMetadata, PageText


class FakeEngine:
    """テスト用 OCREngine 実装。PNG ファイル名から page_number を割り出す."""

    def __init__(self, body_template: str = "OCR text for page {n}") -> None:
        self._body_template = body_template

    @property
    def name(self) -> str:
        return "fake"

    def _one(self, png: Path) -> PageText:
        n = int(png.stem.split("_")[-1])  # page_001.png -> 1
        return PageText(
            page_number=n,
            png_path=png,
            markdown=self._body_template.format(n=n),
            ocr_engine=self.name,
        )

    def run_batch(self, pngs: list[Path]) -> list[PageText]:
        return [self._one(p) for p in pngs]


def _make_meta(out_dir: Path, page_count: int = 2) -> BookMetadata:
    return BookMetadata(
        title="my-book",
        page_count=page_count,
        captured_at=datetime(2026, 4, 28, 21, 0, 0, tzinfo=UTC),
        ocr_engine="fake",
        output_dir=out_dir,
    )


class TestFakeEngineSatisfiesProtocol:
    def test_fake_engine_has_required_methods(self) -> None:
        """Protocol 適合は静的型 (mypy) で担保。実行時は duck typing で確認."""
        engine = FakeEngine()
        assert hasattr(engine, "name")
        assert isinstance(engine.name, str)
        assert callable(engine.run_batch)


class TestOrchestratorRun:
    def test_returns_one_page_per_png(self, tmp_path: Path) -> None:
        meta = _make_meta(tmp_path)
        pngs = [tmp_path / "page_001.png", tmp_path / "page_002.png"]
        engine = FakeEngine()

        pages, _index, _book_md = orchestrator.run(engine, meta, pngs)

        assert len(pages) == 2
        assert pages[0].page_number == 1
        assert pages[1].page_number == 2

    def test_returned_pages_use_engine_name(self, tmp_path: Path) -> None:
        meta = _make_meta(tmp_path)
        pngs = [tmp_path / "page_001.png"]
        engine = FakeEngine()

        pages, _, _ = orchestrator.run(engine, meta, pngs)

        assert pages[0].ocr_engine == "fake"

    def test_index_dict_matches_render_index(self, tmp_path: Path) -> None:
        meta = _make_meta(tmp_path)
        pngs = [tmp_path / "page_001.png", tmp_path / "page_002.png"]
        engine = FakeEngine()

        _, index, _ = orchestrator.run(engine, meta, pngs)

        assert index["title"] == "my-book"
        assert index["page_count"] == 2
        assert index["pages"][0]["png"] == "page_001.png"
        assert index["pages"][1]["md"] == "pages/page_002.md"

    def test_book_md_contains_all_page_markers(self, tmp_path: Path) -> None:
        meta = _make_meta(tmp_path, page_count=3)
        pngs = [tmp_path / f"page_{n:03d}.png" for n in (1, 2, 3)]
        engine = FakeEngine()

        _, _, book_md = orchestrator.run(engine, meta, pngs)

        assert "<!-- page:001 -->" in book_md
        assert "<!-- page:002 -->" in book_md
        assert "<!-- page:003 -->" in book_md
        assert "OCR text for page 1" in book_md
        assert "OCR text for page 3" in book_md

    def test_no_side_effects_on_disk(self, tmp_path: Path) -> None:
        """orchestrator は副作用ゼロ。writer に書き込みを委譲する."""
        meta = _make_meta(tmp_path)
        pngs = [tmp_path / "page_001.png"]
        engine = FakeEngine()

        orchestrator.run(engine, meta, pngs)

        # output_dir 配下に何も書き込まれていないこと
        assert list(tmp_path.iterdir()) == []

    def test_empty_png_paths_returns_empty_lists(self, tmp_path: Path) -> None:
        meta = _make_meta(tmp_path, page_count=0)
        engine = FakeEngine()

        pages, index, book_md = orchestrator.run(engine, meta, [])

        assert pages == []
        assert index["pages"] == []
        assert book_md == ""

    def test_engine_run_batch_called_exactly_once(self, tmp_path: Path) -> None:
        """run_batch が 1 回だけ呼ばれることを確認 (バッチ最適化を保証)."""
        call_count = 0

        class CountingFakeEngine:
            @property
            def name(self) -> str:
                return "fake"

            def run_batch(self, pngs: list[Path]) -> list[PageText]:
                nonlocal call_count
                call_count += 1
                return [
                    PageText(
                        page_number=int(p.stem.split("_")[-1]),
                        png_path=p,
                        markdown="x",
                        ocr_engine=self.name,
                    )
                    for p in pngs
                ]

        meta = _make_meta(tmp_path)
        pngs = [tmp_path / "page_001.png", tmp_path / "page_002.png"]
        orchestrator.run(CountingFakeEngine(), meta, pngs)

        assert call_count == 1


class TestOrchestratorRunInputValidation:
    def test_rejects_engine_returning_wrong_page_number(self, tmp_path: Path) -> None:
        """engine が png ファイル名と一致しない page_number を返した場合の挙動.

        現状仕様: engine が返した PageText をそのまま使う。
        将来的に検証を入れるかは別途判断。今は behavior pinning として残す.
        """

        class BrokenEngine:
            @property
            def name(self) -> str:
                return "broken"

            def run_batch(self, pngs: list[Path]) -> list[PageText]:
                # png のファイル名に関わらず常に page_number=1 を返す
                return [
                    PageText(
                        page_number=1,
                        png_path=p,
                        markdown="x",
                        ocr_engine=self.name,
                    )
                    for p in pngs
                ]

        meta = _make_meta(tmp_path)
        pngs = [tmp_path / "page_001.png", tmp_path / "page_002.png"]

        with pytest.raises(ValueError, match="duplicate"):
            orchestrator.run(BrokenEngine(), meta, pngs)
