"""book_ocr.models の不変性とバリデーションテスト (TDD red)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from book_ocr.models import BookMetadata, PageText


class TestPageText:
    def test_frozen_dataclass_rejects_assignment(self) -> None:
        page = PageText(
            page_number=1,
            png_path=Path("/tmp/page_001.png"),
            markdown="hello",
            ocr_engine="yomitoku",
        )
        with pytest.raises(FrozenInstanceError):
            page.page_number = 2  # type: ignore[misc]

    def test_page_number_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="page_number"):
            PageText(
                page_number=0,
                png_path=Path("/tmp/page_001.png"),
                markdown="x",
                ocr_engine="yomitoku",
            )

    def test_negative_page_number_rejected(self) -> None:
        with pytest.raises(ValueError, match="page_number"):
            PageText(
                page_number=-1,
                png_path=Path("/tmp/page_001.png"),
                markdown="x",
                ocr_engine="yomitoku",
            )

    def test_ocr_engine_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="ocr_engine"):
            PageText(
                page_number=1,
                png_path=Path("/tmp/page_001.png"),
                markdown="x",
                ocr_engine="",
            )

    def test_markdown_can_be_empty(self) -> None:
        page = PageText(
            page_number=1,
            png_path=Path("/tmp/page_001.png"),
            markdown="",
            ocr_engine="yomitoku",
        )
        assert page.markdown == ""


class TestBookMetadata:
    def test_construction_with_required_fields(self) -> None:
        captured = datetime(2026, 4, 28, 21, 0, 0, tzinfo=UTC)
        meta = BookMetadata(
            title="my-book",
            page_count=200,
            captured_at=captured,
            ocr_engine="yomitoku",
            output_dir=Path("/tmp/output/my-book"),
        )
        assert meta.title == "my-book"
        assert meta.page_count == 200
        assert meta.captured_at == captured

    def test_frozen_dataclass_rejects_assignment(self) -> None:
        meta = BookMetadata(
            title="my-book",
            page_count=200,
            captured_at=datetime(2026, 4, 28, tzinfo=UTC),
            ocr_engine="yomitoku",
            output_dir=Path("/tmp/output/my-book"),
        )
        with pytest.raises(FrozenInstanceError):
            meta.title = "other"  # type: ignore[misc]

    def test_title_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="title"):
            BookMetadata(
                title="",
                page_count=200,
                captured_at=datetime(2026, 4, 28, tzinfo=UTC),
                ocr_engine="yomitoku",
                output_dir=Path("/tmp"),
            )

    def test_page_count_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError, match="page_count"):
            BookMetadata(
                title="my-book",
                page_count=-1,
                captured_at=datetime(2026, 4, 28, tzinfo=UTC),
                ocr_engine="yomitoku",
                output_dir=Path("/tmp"),
            )

    def test_page_count_zero_is_allowed(self) -> None:
        """空の本 (キャプチャ失敗時のフォールバック) は許容する."""
        meta = BookMetadata(
            title="empty-book",
            page_count=0,
            captured_at=datetime(2026, 4, 28, tzinfo=UTC),
            ocr_engine="yomitoku",
            output_dir=Path("/tmp"),
        )
        assert meta.page_count == 0

    def test_ocr_engine_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="ocr_engine"):
            BookMetadata(
                title="my-book",
                page_count=200,
                captured_at=datetime(2026, 4, 28, tzinfo=UTC),
                ocr_engine="",
                output_dir=Path("/tmp"),
            )

    # -----------------------------------------------------------------------
    # issue #40: optional reproducibility metadata
    # -----------------------------------------------------------------------

    def test_optional_metadata_defaults_to_none(self) -> None:
        meta = BookMetadata(
            title="my-book",
            page_count=1,
            captured_at=datetime(2026, 4, 28, tzinfo=UTC),
            ocr_engine="yomitoku",
            output_dir=Path("/tmp"),
        )
        assert meta.ocr_engine_version is None
        assert meta.ocr_settings is None
        assert meta.ocr_runtime is None

    def test_optional_metadata_accepts_values(self) -> None:
        meta = BookMetadata(
            title="my-book",
            page_count=1,
            captured_at=datetime(2026, 4, 28, tzinfo=UTC),
            ocr_engine="yomitoku",
            output_dir=Path("/tmp"),
            ocr_engine_version="0.12.0",
            ocr_settings={"device": "mps", "reading_order": "auto"},
            ocr_runtime={"duration_sec": 12.5},
        )
        assert meta.ocr_engine_version == "0.12.0"
        assert meta.ocr_settings == {"device": "mps", "reading_order": "auto"}
        assert meta.ocr_runtime == {"duration_sec": 12.5}
