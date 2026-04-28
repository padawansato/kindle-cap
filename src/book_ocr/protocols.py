"""OCREngine Protocol — 差し替え可能な OCR エンジン抽象."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from book_ocr.models import PageText


@runtime_checkable
class OCREngine(Protocol):
    @property
    def name(self) -> str: ...

    def run(self, png: Path) -> PageText: ...
