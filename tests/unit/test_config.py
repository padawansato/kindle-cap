"""Tests for Config (Spec 06)."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestConfigLoad:
    """Config.load() tests."""

    def test_load_creates_default_if_missing(self, tmp_path: Path) -> None:
        """Should create config file with defaults when it doesn't exist."""
        from kindle_calibre.core.config import Config

        config_path = tmp_path / "config.toml"
        config = Config.load(config_path)
        assert config_path.exists()
        assert config.get("conversion.output_formats") == ["epub", "pdf"]

    def test_load_reads_existing_config(self, tmp_path: Path) -> None:
        """Should read values from existing config file."""
        from kindle_calibre.core.config import Config

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[paths]\ncalibre_library = "/custom/path"\n'
            "[conversion]\noutput_formats = ['epub']\ntimeout_seconds = 600\n"
        )
        config = Config.load(config_path)
        assert config.get("paths.calibre_library") == "/custom/path"
        assert config.get("conversion.timeout_seconds") == 600

    def test_load_raises_on_invalid_toml(self, tmp_path: Path) -> None:
        """Should raise ConfigParseError for invalid TOML."""
        from kindle_calibre.core.config import Config, ConfigParseError

        config_path = tmp_path / "bad.toml"
        config_path.write_text("{{invalid toml!!")
        with pytest.raises(ConfigParseError):
            Config.load(config_path)


class TestConfigGetSet:
    """get() and set() tests."""

    def test_get_dot_notation(self, tmp_path: Path) -> None:
        """Should support dot notation for nested keys."""
        from kindle_calibre.core.config import Config

        config = Config.load(tmp_path / "config.toml")
        assert config.get("paths.calibredb") is not None

    def test_set_and_persist(self, tmp_path: Path) -> None:
        """set() should update value and persist to file."""
        from kindle_calibre.core.config import Config

        config_path = tmp_path / "config.toml"
        config = Config.load(config_path)
        config.set("conversion.timeout_seconds", 999)

        # Reload and verify
        config2 = Config.load(config_path)
        assert config2.get("conversion.timeout_seconds") == 999

    def test_get_missing_key_returns_none(self, tmp_path: Path) -> None:
        """Should return None for non-existent key."""
        from kindle_calibre.core.config import Config

        config = Config.load(tmp_path / "config.toml")
        assert config.get("nonexistent.key") is None


class TestConfigDefaults:
    """Default values tests."""

    def test_all_defaults_present(self, tmp_path: Path) -> None:
        """Fresh config should have all required defaults."""
        from kindle_calibre.core.config import Config

        config = Config.load(tmp_path / "config.toml")
        assert config.get("paths.calibredb") is not None
        assert config.get("paths.ebook_convert") is not None
        assert config.get("paths.calibre_library") is not None
        assert config.get("paths.kindle_mac_dir") is not None
        assert config.get("paths.kindle_device_dir") is not None
        assert config.get("conversion.output_formats") is not None
        assert config.get("conversion.timeout_seconds") is not None
        assert config.get("general.log_level") is not None
