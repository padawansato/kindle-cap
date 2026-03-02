"""Configuration management (Spec 06).

Loads/saves user config from TOML file with sensible defaults.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConfigParseError(Exception):
    """Raised when config file cannot be parsed."""


DEFAULTS: dict[str, dict[str, Any]] = {
    "paths": {
        "calibredb": "/Applications/calibre.app/Contents/MacOS/calibredb",
        "ebook_convert": "/Applications/calibre.app/Contents/MacOS/ebook-convert",
        "calibre_library": str(Path("~/Calibre Library").expanduser()),
        "kindle_mac_dir": str(
            Path(
                "~/Library/Containers/com.amazon.Kindle/Data/Library/"
                "Application Support/Kindle/My Kindle Content"
            ).expanduser()
        ),
        "kindle_device_dir": "/Volumes/Kindle/documents",
    },
    "conversion": {
        "output_formats": ["epub", "pdf"],
        "timeout_seconds": 300,
    },
    "general": {
        "log_level": "info",
    },
}


class Config:
    """Application configuration with TOML persistence."""

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load config from file, creating with defaults if missing.

        Raises:
            ConfigParseError: If file exists but contains invalid TOML.
        """
        raise NotImplementedError("TODO: implement load()")

    def save(self) -> None:
        """Save current config to file."""
        raise NotImplementedError("TODO: implement save()")

    def get(self, key: str) -> Any:
        """Get config value using dot notation (e.g., 'paths.calibredb')."""
        raise NotImplementedError("TODO: implement get()")

    def set(self, key: str, value: Any) -> None:
        """Set config value and persist immediately."""
        raise NotImplementedError("TODO: implement set()")
