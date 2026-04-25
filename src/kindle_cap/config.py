"""Configuration data classes for kindle_cap."""
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Direction(StrEnum):
    RTL = "rtl"
    LTR = "ltr"


@dataclass(frozen=True)
class Geometry:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class CaptureConfig:
    name: str
    pages: int
    direction: Direction
    wait: float
    out: Path
    keep_png: bool

    def __post_init__(self) -> None:
        if self.pages <= 0:
            raise ValueError("pages must be positive")
        if self.wait < 0:
            raise ValueError("wait must be non-negative")
        if not self.name:
            raise ValueError("name must be non-empty")
        if "/" in self.name:
            raise ValueError("name must not contain '/'")
        if "\x00" in self.name:
            raise ValueError("name must not contain null bytes")
        if self.name in (".", ".."):
            raise ValueError("name must not be '.' or '..'")
