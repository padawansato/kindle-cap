"""Tests for ProcessedRegistry (Spec 03)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestRegistryIsProcessed:
    """is_processed() tests."""

    def test_unprocessed_file_returns_false(
        self, empty_registry_file: Path, sample_azw3_file: Path
    ) -> None:
        """New file should not be marked as processed."""
        from kindle_calibre.core.registry import ProcessedRegistry
        from kindle_calibre.core.scanner import KindleFile

        registry = ProcessedRegistry(empty_registry_file)
        kindle_file = _make_kindle_file(sample_azw3_file)
        assert registry.is_processed(kindle_file) is False

    def test_processed_file_returns_true(
        self, empty_registry_file: Path, sample_azw3_file: Path
    ) -> None:
        """Marked file should be detected as processed."""
        from kindle_calibre.core.registry import ProcessedRegistry
        from kindle_calibre.core.scanner import KindleFile

        registry = ProcessedRegistry(empty_registry_file)
        kindle_file = _make_kindle_file(sample_azw3_file)
        registry.mark_processed(kindle_file, calibre_id=1, formats=["epub"], source="test")
        assert registry.is_processed(kindle_file) is True


class TestRegistryMarkProcessed:
    """mark_processed() tests."""

    def test_persists_to_file(
        self, empty_registry_file: Path, sample_azw3_file: Path
    ) -> None:
        """Should write to JSON file immediately."""
        from kindle_calibre.core.registry import ProcessedRegistry

        registry = ProcessedRegistry(empty_registry_file)
        kindle_file = _make_kindle_file(sample_azw3_file)
        registry.mark_processed(kindle_file, calibre_id=42, formats=["epub", "pdf"], source="mac")

        # Read file directly
        data = json.loads(empty_registry_file.read_text())
        assert len(data["entries"]) == 1
        entry = list(data["entries"].values())[0]
        assert entry["calibre_id"] == 42
        assert entry["formats"] == ["epub", "pdf"]

    def test_multiple_entries(
        self, empty_registry_file: Path, sample_azw3_file: Path, sample_kfx_file: Path
    ) -> None:
        """Should track multiple files."""
        from kindle_calibre.core.registry import ProcessedRegistry

        registry = ProcessedRegistry(empty_registry_file)
        f1 = _make_kindle_file(sample_azw3_file)
        f2 = _make_kindle_file(sample_kfx_file)
        registry.mark_processed(f1, calibre_id=1, formats=["epub"], source="mac")
        registry.mark_processed(f2, calibre_id=2, formats=["pdf"], source="device")
        assert registry.is_processed(f1)
        assert registry.is_processed(f2)


class TestRegistryGetStats:
    """get_stats() tests."""

    def test_empty_registry_stats(self, empty_registry_file: Path) -> None:
        """Empty registry should return zero counts."""
        from kindle_calibre.core.registry import ProcessedRegistry

        registry = ProcessedRegistry(empty_registry_file)
        stats = registry.get_stats()
        assert stats.total_processed == 0
        assert stats.last_processed_at is None

    def test_stats_after_processing(
        self, empty_registry_file: Path, sample_azw3_file: Path
    ) -> None:
        """Should reflect processed entries."""
        from kindle_calibre.core.registry import ProcessedRegistry

        registry = ProcessedRegistry(empty_registry_file)
        kindle_file = _make_kindle_file(sample_azw3_file)
        registry.mark_processed(kindle_file, calibre_id=1, formats=["epub", "pdf"], source="mac")
        stats = registry.get_stats()
        assert stats.total_processed == 1
        assert stats.last_processed_at is not None


class TestRegistryReset:
    """reset() tests."""

    def test_reset_clears_entries(
        self, empty_registry_file: Path, sample_azw3_file: Path
    ) -> None:
        """Should remove all entries."""
        from kindle_calibre.core.registry import ProcessedRegistry

        registry = ProcessedRegistry(empty_registry_file)
        kindle_file = _make_kindle_file(sample_azw3_file)
        registry.mark_processed(kindle_file, calibre_id=1, formats=["epub"], source="mac")
        registry.reset()
        assert registry.is_processed(kindle_file) is False
        assert registry.get_stats().total_processed == 0


class TestRegistryRobustness:
    """Edge cases and robustness tests."""

    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        """Should create registry file if it doesn't exist."""
        from kindle_calibre.core.registry import ProcessedRegistry

        path = tmp_path / "new" / "processed.json"
        registry = ProcessedRegistry(path)
        assert path.exists()

    def test_handles_corrupted_json(self, tmp_path: Path) -> None:
        """Should recover from corrupted JSON file."""
        from kindle_calibre.core.registry import ProcessedRegistry

        path = tmp_path / "corrupted.json"
        path.write_text("{invalid json!!")
        registry = ProcessedRegistry(path)
        # Should initialize empty without crashing
        assert registry.get_stats().total_processed == 0


def _make_kindle_file(path: Path) -> "KindleFile":
    """Helper to create a KindleFile from a path."""
    import hashlib
    from datetime import datetime

    from kindle_calibre.core.scanner import KindleFile

    content = path.read_bytes()
    return KindleFile(
        path=path,
        format=path.suffix.lstrip(".").lower(),
        size_bytes=len(content),
        modified_at=datetime.fromtimestamp(path.stat().st_mtime),
        md5_hash=hashlib.md5(content).hexdigest(),
    )
