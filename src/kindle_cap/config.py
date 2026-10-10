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
    direction: Direction | None
    wait: float
    out: Path
    keep_png: bool
    pdf_jpeg_quality: int | None = None
    progress: bool = False
    # issue #69: 撮影矩形の上端から削る量 (論理ポイント)。タイトルバー / 信号機ボタン除外用
    crop_top: int = 0
    # issue #84: True なら Kindle を前面に出さず、窓 ID 指定キャプチャ + pid 宛てキーで撮る
    background: bool = True

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
        if self.pdf_jpeg_quality is not None and not (1 <= self.pdf_jpeg_quality <= 100):
            raise ValueError(f"pdf_jpeg_quality must be in 1..100 (got {self.pdf_jpeg_quality})")
        if self.crop_top < 0:
            raise ValueError(f"crop_top must be >= 0 (got {self.crop_top})")
