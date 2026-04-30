"""Domain value objects for book_ocr."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class PageText:
    page_number: int
    png_path: Path
    markdown: str
    ocr_engine: str

    def __post_init__(self) -> None:
        if self.page_number <= 0:
            raise ValueError(f"page_number must be positive, got {self.page_number}")
        if not self.ocr_engine:
            raise ValueError("ocr_engine must be non-empty")


@dataclass(frozen=True)
class BookMetadata:
    title: str
    page_count: int
    captured_at: datetime
    ocr_engine: str
    output_dir: Path

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("title must be non-empty")
        if self.page_count < 0:
            raise ValueError(f"page_count must be >= 0, got {self.page_count}")
        if not self.ocr_engine:
            raise ValueError("ocr_engine must be non-empty")
