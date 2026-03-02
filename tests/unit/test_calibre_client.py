"""Tests for CalibreClient (Spec 02)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCalibreClientInit:
    """Constructor and verify tests."""

    def test_raises_if_calibredb_not_found(self, tmp_path: Path) -> None:
        """Should raise CalibreNotFoundError if binary doesn't exist."""
        from kindle_calibre.core.calibre import CalibreClient, CalibreNotFoundError

        with pytest.raises(CalibreNotFoundError):
            CalibreClient(
                calibredb_path=tmp_path / "nonexistent",
                ebook_convert_path=tmp_path / "nonexistent",
                library_path=tmp_path,
            )

    def test_verify_success(self, tmp_path: Path) -> None:
        """verify() should return True when calibredb responds."""
        from kindle_calibre.core.calibre import CalibreClient

        # Create fake binaries
        calibredb = tmp_path / "calibredb"
        calibredb.write_text("#!/bin/bash\necho 'calibre 7.0'")
        calibredb.chmod(0o755)
        convert = tmp_path / "ebook-convert"
        convert.write_text("#!/bin/bash\necho 'ok'")
        convert.chmod(0o755)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="calibre 7.0", stderr=""
            )
            client = CalibreClient(
                calibredb_path=calibredb,
                ebook_convert_path=convert,
                library_path=tmp_path,
            )
            assert client.verify() is True


class TestCalibreClientAddBook:
    """add_book() method tests."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> "CalibreClient":
        from kindle_calibre.core.calibre import CalibreClient

        calibredb = tmp_path / "calibredb"
        calibredb.write_text("#!/bin/bash\necho ok")
        calibredb.chmod(0o755)
        convert = tmp_path / "ebook-convert"
        convert.write_text("#!/bin/bash\necho ok")
        convert.chmod(0o755)
        lib = tmp_path / "library"
        lib.mkdir()
        return CalibreClient(
            calibredb_path=calibredb,
            ebook_convert_path=convert,
            library_path=lib,
        )

    def test_add_book_success(self, client: "CalibreClient", sample_azw3_file: Path) -> None:
        """Should return AddResult with book_id on success."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Added book ids: 42",
                stderr="",
            )
            result = client.add_book(sample_azw3_file)
            assert result.success is True
            assert result.book_id == 42
            assert result.duplicate is False

    def test_add_book_duplicate(self, client: "CalibreClient", sample_azw3_file: Path) -> None:
        """Should return duplicate=True for already existing book."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Added book ids: ",
                stderr="already exist in the library",
            )
            result = client.add_book(sample_azw3_file)
            assert result.duplicate is True

    def test_add_book_failure(self, client: "CalibreClient", sample_azw3_file: Path) -> None:
        """Should return success=False on command failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="DRM error",
            )
            result = client.add_book(sample_azw3_file)
            assert result.success is False
            assert result.error_message is not None


class TestCalibreClientConvert:
    """convert_book() method tests."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> "CalibreClient":
        from kindle_calibre.core.calibre import CalibreClient

        calibredb = tmp_path / "calibredb"
        calibredb.write_text("#!/bin/bash\necho ok")
        calibredb.chmod(0o755)
        convert = tmp_path / "ebook-convert"
        convert.write_text("#!/bin/bash\necho ok")
        convert.chmod(0o755)
        lib = tmp_path / "library"
        lib.mkdir()
        return CalibreClient(
            calibredb_path=calibredb,
            ebook_convert_path=convert,
            library_path=lib,
        )

    def test_convert_epub_success(self, client: "CalibreClient", tmp_path: Path) -> None:
        """Should return ConvertResult with output path on success."""
        input_file = tmp_path / "book.azw3"
        input_file.write_bytes(b"CONTENT")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Output saved", stderr="")
            result = client.convert_book(book_id=42, output_format="epub")
            assert result.success is True

    def test_convert_failure(self, client: "CalibreClient") -> None:
        """Should return success=False on conversion failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Conversion failed"
            )
            result = client.convert_book(book_id=42, output_format="epub")
            assert result.success is False

    def test_convert_timeout(self, client: "CalibreClient") -> None:
        """Should handle subprocess timeout gracefully."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="", timeout=300)):
            result = client.convert_book(book_id=42, output_format="pdf")
            assert result.success is False
            assert "timeout" in (result.error_message or "").lower()


class TestCalibreClientListBooks:
    """list_books() method tests."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> "CalibreClient":
        from kindle_calibre.core.calibre import CalibreClient

        calibredb = tmp_path / "calibredb"
        calibredb.write_text("#!/bin/bash\necho ok")
        calibredb.chmod(0o755)
        convert = tmp_path / "ebook-convert"
        convert.write_text("#!/bin/bash\necho ok")
        convert.chmod(0o755)
        lib = tmp_path / "library"
        lib.mkdir()
        return CalibreClient(
            calibredb_path=calibredb,
            ebook_convert_path=convert,
            library_path=lib,
        )

    def test_list_books_returns_books(self, client: "CalibreClient") -> None:
        """Should parse calibredb list output into CalibreBook objects."""
        csv_output = (
            "id,title,authors,formats\n"
            '1,"Test Book","Author One","[EPUB, PDF]"\n'
            '2,"Another","Author Two","[AZW3]"\n'
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=csv_output, stderr="")
            books = client.list_books()
            assert len(books) >= 2

    def test_list_books_empty_library(self, client: "CalibreClient") -> None:
        """Should return empty list for empty library."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="id,title,authors,formats\n", stderr=""
            )
            books = client.list_books()
            assert books == []
