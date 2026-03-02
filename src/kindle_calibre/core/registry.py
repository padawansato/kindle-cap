"""Processed file registry (Spec 03).

Tracks which Kindle files have been processed to avoid duplicates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kindle_calibre.core.scanner import KindleFile

logger = logging.getLogger(__name__)


@dataclass
class RegistryStats:
    """Summary statistics for the registry."""

    total_processed: int
    last_processed_at: datetime | None
    formats_count: dict[str, int]


class ProcessedRegistry:
    """Manages the record of processed Kindle files.

    Storage: JSON file at the specified path.
    Key: MD5 hash of the original file.
    """

    def __init__(self, path: Path) -> None:
        """Initialize registry, creating file if needed.

        If the JSON file is corrupted, backs it up and starts fresh.
        """
        raise NotImplementedError("TODO: implement __init__()")

    def is_processed(self, file: KindleFile) -> bool:
        """Check if a file has already been processed."""
        raise NotImplementedError("TODO: implement is_processed()")

    def mark_processed(
        self,
        file: KindleFile,
        calibre_id: int,
        formats: list[str],
        source: str,
    ) -> None:
        """Record a file as processed. Persists immediately."""
        raise NotImplementedError("TODO: implement mark_processed()")

    def get_stats(self) -> RegistryStats:
        """Return summary statistics."""
        raise NotImplementedError("TODO: implement get_stats()")

    def reset(self) -> None:
        """Clear all entries."""
        raise NotImplementedError("TODO: implement reset()")
