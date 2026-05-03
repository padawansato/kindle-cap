from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from book_ocr.models import BookMetadata


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("-m", default=""):
        return
    skip_live = pytest.mark.skip(reason="needs Kindle running; use `pytest -m live`")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def make_meta() -> Callable[..., BookMetadata]:
    """テスト用 BookMetadata factory.

    test_book_ocr_orchestrator.py / test_book_ocr_exporters.py で重複していた
    `_make_meta` を集約 (issue #23)。呼び出し側で `out_dir` / `ocr_engine` /
    `page_count` / `title` を override できる。`captured_at` は決定論のため固定値。
    """

    def _make(
        out_dir: Path = Path("/tmp/output/my-book"),
        page_count: int = 2,
        ocr_engine: str = "yomitoku",
        title: str = "my-book",
    ) -> BookMetadata:
        return BookMetadata(
            title=title,
            page_count=page_count,
            captured_at=datetime(2026, 4, 28, 21, 0, 0, tzinfo=UTC),
            ocr_engine=ocr_engine,
            output_dir=out_dir,
        )

    return _make
