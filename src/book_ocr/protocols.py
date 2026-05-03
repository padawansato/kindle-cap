"""OCREngine Protocol — 差し替え可能な OCR エンジン抽象."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from book_ocr.models import PageText


class OCREngine(Protocol):
    @property
    def name(self) -> str: ...

    def run_batch(self, pngs: list[Path]) -> list[PageText]: ...
