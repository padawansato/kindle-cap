"""Tests for BookConverter (Spec 04)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestConvertOne:
    """convert_one() tests."""

    def test_skips_already_processed(self, sample_azw3_file: Path) -> None:
        """Should skip files already in the registry."""
        from kindle_calibre.core.converter import BookConverter

        mock_calibre = MagicMock()
        mock_registry = MagicMock()
        mock_registry.is_processed.return_value = True

        converter = BookConverter(calibre=mock_calibre, registry=mock_registry)
        kindle_file = _make_kindle_file(sample_azw3_file)
        report = converter.convert_one(kindle_file, formats=["epub", "pdf"])

        assert report.skipped is True
        mock_calibre.add_book.assert_not_called()

    def test_adds_and_converts_new_file(self, sample_azw3_file: Path) -> None:
        """Should add to Calibre and convert to requested formats."""
        from kindle_calibre.core.calibre import AddResult, ConvertResult
        from kindle_calibre.core.converter import BookConverter

        mock_calibre = MagicMock()
        mock_calibre.add_book.return_value = AddResult(
            success=True, book_id=42, duplicate=False, error_message=None
        )
        mock_calibre.convert_book.return_value = ConvertResult(
            success=True, output_path=Path("/tmp/out.epub"), error_message=None
        )
        mock_calibre.add_format.return_value = True

        mock_registry = MagicMock()
        mock_registry.is_processed.return_value = False

        converter = BookConverter(calibre=mock_calibre, registry=mock_registry)
        kindle_file = _make_kindle_file(sample_azw3_file)
        report = converter.convert_one(kindle_file, formats=["epub", "pdf"])

        assert report.skipped is False
        assert report.calibre_id == 42
        assert mock_calibre.convert_book.call_count == 2  # epub + pdf
        mock_registry.mark_processed.assert_called_once()

    def test_handles_add_failure(self, sample_azw3_file: Path) -> None:
        """Should report error when add_book fails."""
        from kindle_calibre.core.calibre import AddResult
        from kindle_calibre.core.converter import BookConverter

        mock_calibre = MagicMock()
        mock_calibre.add_book.return_value = AddResult(
            success=False, book_id=None, duplicate=False, error_message="DRM error"
        )

        mock_registry = MagicMock()
        mock_registry.is_processed.return_value = False

        converter = BookConverter(calibre=mock_calibre, registry=mock_registry)
        kindle_file = _make_kindle_file(sample_azw3_file)
        report = converter.convert_one(kindle_file, formats=["epub"])

        assert report.error is not None
        assert report.calibre_id is None
        mock_registry.mark_processed.assert_not_called()

    def test_partial_conversion_failure(self, sample_azw3_file: Path) -> None:
        """Should report which formats succeeded and which failed."""
        from kindle_calibre.core.calibre import AddResult, ConvertResult
        from kindle_calibre.core.converter import BookConverter

        mock_calibre = MagicMock()
        mock_calibre.add_book.return_value = AddResult(
            success=True, book_id=42, duplicate=False, error_message=None
        )
        # epub succeeds, pdf fails
        mock_calibre.convert_book.side_effect = [
            ConvertResult(success=True, output_path=Path("/tmp/out.epub"), error_message=None),
            ConvertResult(success=False, output_path=None, error_message="PDF conversion failed"),
        ]
        mock_calibre.add_format.return_value = True

        mock_registry = MagicMock()
        mock_registry.is_processed.return_value = False

        converter = BookConverter(calibre=mock_calibre, registry=mock_registry)
        kindle_file = _make_kindle_file(sample_azw3_file)
        report = converter.convert_one(kindle_file, formats=["epub", "pdf"])

        assert "epub" in report.converted_formats
        assert "pdf" in report.failed_formats


class TestConvertBatch:
    """convert_batch() tests."""

    def test_batch_processes_all_files(self, populated_kindle_dir: Path) -> None:
        """Should process all files and return BatchReport."""
        from kindle_calibre.core.calibre import AddResult, ConvertResult
        from kindle_calibre.core.converter import BookConverter

        mock_calibre = MagicMock()
        mock_calibre.add_book.return_value = AddResult(
            success=True, book_id=1, duplicate=False, error_message=None
        )
        mock_calibre.convert_book.return_value = ConvertResult(
            success=True, output_path=Path("/tmp/out.epub"), error_message=None
        )
        mock_calibre.add_format.return_value = True

        mock_registry = MagicMock()
        mock_registry.is_processed.return_value = False

        converter = BookConverter(calibre=mock_calibre, registry=mock_registry)

        from kindle_calibre.core.scanner import KindleScanner

        scanner = KindleScanner()
        files = scanner.scan(populated_kindle_dir)

        report = converter.convert_batch(files, formats=["epub"], on_progress=lambda *a: None)
        assert report.total == len(files)
        assert report.success + report.skipped + report.failed == report.total

    def test_batch_continues_on_error(self, tmp_path: Path) -> None:
        """Should not stop on single file failure."""
        from kindle_calibre.core.calibre import AddResult
        from kindle_calibre.core.converter import BookConverter

        mock_calibre = MagicMock()
        # First fails, second succeeds
        mock_calibre.add_book.side_effect = [
            AddResult(success=False, book_id=None, duplicate=False, error_message="Error"),
            AddResult(success=True, book_id=2, duplicate=False, error_message=None),
        ]
        mock_calibre.convert_book.return_value = MagicMock(success=True, output_path=Path("/tmp/x"))
        mock_calibre.add_format.return_value = True

        mock_registry = MagicMock()
        mock_registry.is_processed.return_value = False

        converter = BookConverter(calibre=mock_calibre, registry=mock_registry)

        d = tmp_path / "books"
        d.mkdir()
        (d / "a.azw3").write_bytes(b"A")
        (d / "b.azw3").write_bytes(b"B")
        files = [_make_kindle_file(d / "a.azw3"), _make_kindle_file(d / "b.azw3")]

        report = converter.convert_batch(files, formats=["epub"], on_progress=lambda *a: None)
        assert report.failed == 1
        assert report.success == 1

    def test_batch_calls_progress_callback(self, sample_azw3_file: Path) -> None:
        """Should call on_progress for each file."""
        from kindle_calibre.core.calibre import AddResult, ConvertResult
        from kindle_calibre.core.converter import BookConverter

        mock_calibre = MagicMock()
        mock_calibre.add_book.return_value = AddResult(
            success=True, book_id=1, duplicate=False, error_message=None
        )
        mock_calibre.convert_book.return_value = ConvertResult(
            success=True, output_path=Path("/tmp/out"), error_message=None
        )
        mock_calibre.add_format.return_value = True

        mock_registry = MagicMock()
        mock_registry.is_processed.return_value = False

        progress_calls: list = []
        converter = BookConverter(calibre=mock_calibre, registry=mock_registry)
        files = [_make_kindle_file(sample_azw3_file)]
        converter.convert_batch(files, formats=["epub"], on_progress=lambda *a: progress_calls.append(a))
        assert len(progress_calls) >= 1


def _make_kindle_file(path: Path) -> "KindleFile":
    """Helper to create a KindleFile from a path."""
    from kindle_calibre.core.scanner import KindleFile

    content = path.read_bytes()
    return KindleFile(
        path=path,
        format=path.suffix.lstrip(".").lower(),
        size_bytes=len(content),
        modified_at=datetime.fromtimestamp(path.stat().st_mtime),
        md5_hash=hashlib.md5(content).hexdigest(),
    )
