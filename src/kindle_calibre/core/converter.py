"""Format conversion pipeline (Spec 04).

Orchestrates the full pipeline: scan → add → convert → register.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from kindle_calibre.core.calibre import CalibreClient
from kindle_calibre.core.registry import ProcessedRegistry
from kindle_calibre.core.scanner import KindleFile

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], Any]  # (current, total, filename)


@dataclass
class ConversionReport:
    """Result of processing a single book."""

    file: KindleFile
    calibre_id: int | None = None
    converted_formats: list[str] = field(default_factory=list)
    failed_formats: list[str] = field(default_factory=list)
    skipped: bool = False
    error: str | None = None


@dataclass
class BatchReport:
    """Result of processing multiple books."""

    total: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    reports: list[ConversionReport] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class BookConverter:
    """Converts Kindle files and registers them in Calibre."""

    def __init__(self, calibre: CalibreClient, registry: ProcessedRegistry) -> None:
        self._calibre = calibre
        self._registry = registry

    def convert_one(self, file: KindleFile, formats: list[str]) -> ConversionReport:
        """Process a single Kindle file.

        1. Check registry (skip if processed)
        2. Add to Calibre via calibredb add
        3. Convert to each requested format
        4. Register as processed
        """
        raise NotImplementedError("TODO: implement convert_one()")

    def convert_batch(
        self,
        files: list[KindleFile],
        formats: list[str],
        on_progress: ProgressCallback,
    ) -> BatchReport:
        """Process multiple files with progress reporting.

        Continues on individual file errors.
        Processes smallest files first for early feedback.
        """
        raise NotImplementedError("TODO: implement convert_batch()")
