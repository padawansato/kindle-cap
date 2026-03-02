"""Kindle file scanner (Spec 01).

Detects Kindle book files (.azw, .azw3, .kfx, .mobi) in specified directories.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

KINDLE_EXTENSIONS = {".azw", ".azw3", ".kfx", ".mobi"}


class DirectoryNotFoundError(Exception):
    """Raised when a scan directory does not exist."""


@dataclass
class KindleFile:
    """Represents a detected Kindle book file."""

    path: Path
    format: str  # "azw", "azw3", "kfx", "mobi"
    size_bytes: int
    modified_at: datetime
    md5_hash: str


class KindleScanner:
    """Scans directories for Kindle book files."""

    def scan(self, directory: Path) -> list[KindleFile]:
        """Scan a directory recursively for Kindle files.

        Args:
            directory: Directory to scan.

        Returns:
            List of detected KindleFile objects.

        Raises:
            DirectoryNotFoundError: If directory does not exist.
        """
        raise NotImplementedError("TODO: implement scan()")

    def scan_multiple(self, directories: list[Path]) -> list[KindleFile]:
        """Scan multiple directories and merge results.

        Skips non-existent directories with a warning.
        Deduplicates by file path.

        Args:
            directories: List of directories to scan.

        Returns:
            Merged, deduplicated list of KindleFile objects.
        """
        raise NotImplementedError("TODO: implement scan_multiple()")
