"""Shared test fixtures."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def tmp_kindle_dir(tmp_path: Path) -> Path:
    """Create a temporary directory simulating Kindle content folder."""
    kindle_dir = tmp_path / "kindle_content"
    kindle_dir.mkdir()
    return kindle_dir


@pytest.fixture
def tmp_calibre_library(tmp_path: Path) -> Path:
    """Create a temporary Calibre library directory."""
    lib_dir = tmp_path / "Calibre Library"
    lib_dir.mkdir()
    return lib_dir


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_azw3_file(tmp_kindle_dir: Path) -> Path:
    """Create a dummy .azw3 file."""
    f = tmp_kindle_dir / "sample_book.azw3"
    f.write_bytes(b"FAKE_AZW3_CONTENT_FOR_TESTING")
    return f


@pytest.fixture
def sample_kfx_file(tmp_kindle_dir: Path) -> Path:
    """Create a dummy .kfx file."""
    f = tmp_kindle_dir / "another_book.kfx"
    f.write_bytes(b"FAKE_KFX_CONTENT_FOR_TESTING")
    return f


@pytest.fixture
def sample_mobi_file(tmp_kindle_dir: Path) -> Path:
    """Create a dummy .mobi file."""
    f = tmp_kindle_dir / "classic.mobi"
    f.write_bytes(b"FAKE_MOBI_CONTENT_FOR_TESTING")
    return f


@pytest.fixture
def empty_registry_file(tmp_config_dir: Path) -> Path:
    """Create an empty registry JSON file."""
    f = tmp_config_dir / "processed.json"
    f.write_text(json.dumps({"version": 1, "entries": {}}))
    return f


@pytest.fixture
def populated_kindle_dir(tmp_kindle_dir: Path) -> Path:
    """Create a Kindle directory with multiple book files."""
    (tmp_kindle_dir / "book1.azw3").write_bytes(b"BOOK1_CONTENT")
    (tmp_kindle_dir / "book2.azw").write_bytes(b"BOOK2_CONTENT")
    (tmp_kindle_dir / "book3.kfx").write_bytes(b"BOOK3_CONTENT")
    (tmp_kindle_dir / "book4.mobi").write_bytes(b"BOOK4_CONTENT")
    (tmp_kindle_dir / "not_a_book.txt").write_text("ignore me")
    (tmp_kindle_dir / "readme.pdf").write_bytes(b"PDF_CONTENT")
    sub = tmp_kindle_dir / "subdir"
    sub.mkdir()
    (sub / "nested_book.azw3").write_bytes(b"NESTED_CONTENT")
    return tmp_kindle_dir
