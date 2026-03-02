"""Calibre CLI client wrapper (Spec 02).

Wraps calibredb and ebook-convert CLI tools.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class CalibreNotFoundError(Exception):
    """Raised when Calibre CLI binaries are not found."""


class CalibreCommandError(Exception):
    """Raised when a Calibre CLI command fails."""


class CalibreOutputParseError(Exception):
    """Raised when Calibre CLI output cannot be parsed."""


@dataclass
class AddResult:
    """Result of adding a book to Calibre."""

    success: bool
    book_id: int | None
    duplicate: bool
    error_message: str | None


@dataclass
class ConvertResult:
    """Result of converting a book format."""

    success: bool
    output_path: Path | None
    error_message: str | None


@dataclass
class CalibreBook:
    """A book in the Calibre library."""

    id: int
    title: str
    authors: list[str]
    formats: list[str]


class CalibreClient:
    """Client for interacting with Calibre CLI tools."""

    def __init__(
        self,
        calibredb_path: Path = Path("/Applications/calibre.app/Contents/MacOS/calibredb"),
        ebook_convert_path: Path = Path("/Applications/calibre.app/Contents/MacOS/ebook-convert"),
        library_path: Path = Path("~/Calibre Library").expanduser(),
        timeout: int = 300,
    ) -> None:
        """Initialize CalibreClient.

        Raises:
            CalibreNotFoundError: If CLI binaries are not found at specified paths.
        """
        raise NotImplementedError("TODO: implement __init__()")

    def verify(self) -> bool:
        """Verify that Calibre CLI is accessible and working."""
        raise NotImplementedError("TODO: implement verify()")

    def add_book(self, file: Path) -> AddResult:
        """Add a book file to the Calibre library.

        DeDRM plugin handles DRM removal automatically (Calibre-side config).
        """
        raise NotImplementedError("TODO: implement add_book()")

    def convert_book(self, book_id: int, output_format: str) -> ConvertResult:
        """Convert a book to the specified format using ebook-convert."""
        raise NotImplementedError("TODO: implement convert_book()")

    def add_format(self, book_id: int, file: Path) -> bool:
        """Add a format file to an existing book in the library."""
        raise NotImplementedError("TODO: implement add_format()")

    def list_books(self) -> list[CalibreBook]:
        """List all books in the Calibre library."""
        raise NotImplementedError("TODO: implement list_books()")
