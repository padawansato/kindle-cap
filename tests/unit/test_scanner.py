"""Tests for KindleScanner (Spec 01)."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestKindleScannerScan:
    """scan() method tests."""

    def test_finds_azw3_files(self, populated_kindle_dir: Path) -> None:
        """Should detect .azw3 files."""
        from kindle_calibre.core.scanner import KindleScanner

        scanner = KindleScanner()
        results = scanner.scan(populated_kindle_dir)
        azw3_files = [f for f in results if f.format == "azw3"]
        assert len(azw3_files) >= 1

    def test_finds_all_kindle_formats(self, populated_kindle_dir: Path) -> None:
        """Should detect .azw, .azw3, .kfx, .mobi files."""
        from kindle_calibre.core.scanner import KindleScanner

        scanner = KindleScanner()
        results = scanner.scan(populated_kindle_dir)
        formats = {f.format for f in results}
        assert formats == {"azw", "azw3", "kfx", "mobi"}

    def test_ignores_non_kindle_files(self, populated_kindle_dir: Path) -> None:
        """Should not include .txt, .pdf, etc."""
        from kindle_calibre.core.scanner import KindleScanner

        scanner = KindleScanner()
        results = scanner.scan(populated_kindle_dir)
        extensions = {f.format for f in results}
        assert "txt" not in extensions
        assert "pdf" not in extensions

    def test_scans_recursively(self, populated_kindle_dir: Path) -> None:
        """Should find files in subdirectories."""
        from kindle_calibre.core.scanner import KindleScanner

        scanner = KindleScanner()
        results = scanner.scan(populated_kindle_dir)
        nested = [f for f in results if "nested" in f.path.name]
        assert len(nested) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Should return empty list for empty directory."""
        from kindle_calibre.core.scanner import KindleScanner

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        scanner = KindleScanner()
        results = scanner.scan(empty_dir)
        assert results == []

    def test_nonexistent_directory_raises(self, tmp_path: Path) -> None:
        """Should raise DirectoryNotFoundError for missing directory."""
        from kindle_calibre.core.scanner import KindleScanner

        scanner = KindleScanner()
        with pytest.raises(Exception):  # DirectoryNotFoundError
            scanner.scan(tmp_path / "nonexistent")

    def test_case_insensitive_extension(self, tmp_path: Path) -> None:
        """Should detect .AZW3 (uppercase) files."""
        from kindle_calibre.core.scanner import KindleScanner

        d = tmp_path / "mixed_case"
        d.mkdir()
        (d / "UPPER.AZW3").write_bytes(b"CONTENT")
        scanner = KindleScanner()
        results = scanner.scan(d)
        assert len(results) == 1

    def test_skips_zero_byte_files(self, tmp_path: Path) -> None:
        """Should skip 0-byte files."""
        from kindle_calibre.core.scanner import KindleScanner

        d = tmp_path / "zero"
        d.mkdir()
        (d / "empty.azw3").write_bytes(b"")
        scanner = KindleScanner()
        results = scanner.scan(d)
        assert len(results) == 0

    def test_kindle_file_has_md5_hash(self, sample_azw3_file: Path) -> None:
        """KindleFile should contain a valid MD5 hash."""
        from kindle_calibre.core.scanner import KindleScanner

        scanner = KindleScanner()
        results = scanner.scan(sample_azw3_file.parent)
        assert len(results) == 1
        assert len(results[0].md5_hash) == 32  # MD5 hex digest length

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Should not scan inside hidden directories."""
        from kindle_calibre.core.scanner import KindleScanner

        d = tmp_path / "with_hidden"
        d.mkdir()
        hidden = d / ".hidden"
        hidden.mkdir()
        (hidden / "secret.azw3").write_bytes(b"HIDDEN")
        (d / "visible.azw3").write_bytes(b"VISIBLE")
        scanner = KindleScanner()
        results = scanner.scan(d)
        assert len(results) == 1
        assert results[0].path.name == "visible.azw3"


class TestKindleScannerScanMultiple:
    """scan_multiple() method tests."""

    def test_merges_results(self, tmp_path: Path) -> None:
        """Should combine results from multiple directories."""
        from kindle_calibre.core.scanner import KindleScanner

        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "a.azw3").write_bytes(b"A")
        (d2 / "b.mobi").write_bytes(b"B")
        scanner = KindleScanner()
        results = scanner.scan_multiple([d1, d2])
        assert len(results) == 2

    def test_skips_nonexistent_directories(self, tmp_path: Path) -> None:
        """Should skip missing directories without error."""
        from kindle_calibre.core.scanner import KindleScanner

        d1 = tmp_path / "exists"
        d1.mkdir()
        (d1 / "a.azw3").write_bytes(b"A")
        scanner = KindleScanner()
        results = scanner.scan_multiple([d1, tmp_path / "nope"])
        assert len(results) == 1

    def test_deduplicates_same_path(self, tmp_path: Path) -> None:
        """Should not include the same file twice."""
        from kindle_calibre.core.scanner import KindleScanner

        d = tmp_path / "dup"
        d.mkdir()
        (d / "book.azw3").write_bytes(b"X")
        scanner = KindleScanner()
        results = scanner.scan_multiple([d, d])
        assert len(results) == 1
