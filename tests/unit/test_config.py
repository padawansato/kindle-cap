from pathlib import Path
from typing import Any

import pytest

from kindle_cap.config import CaptureConfig, Direction, Geometry

# ---------------------------------------------------------------------------
# Direction
# ---------------------------------------------------------------------------


def test_direction_string_values() -> None:
    assert Direction.RTL.value == "rtl"
    assert Direction.LTR.value == "ltr"


def test_direction_has_only_two_values() -> None:
    assert set(Direction) == {Direction.RTL, Direction.LTR}


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def test_geometry_holds_values() -> None:
    g = Geometry(x=0, y=31, width=1440, height=869)
    assert g.x == 0
    assert g.y == 31
    assert g.width == 1440
    assert g.height == 869


def test_geometry_is_frozen() -> None:
    g = Geometry(x=0, y=0, width=100, height=100)
    with pytest.raises(Exception):
        g.x = 99  # type: ignore[misc]


def test_geometry_equality_by_value() -> None:
    assert Geometry(0, 0, 100, 100) == Geometry(0, 0, 100, 100)
    assert Geometry(0, 0, 100, 100) != Geometry(1, 0, 100, 100)


def test_geometry_hashable() -> None:
    """frozen dataclass はハッシュ可能"""
    s = {Geometry(0, 0, 100, 100), Geometry(0, 0, 100, 100)}
    assert len(s) == 1


# ---------------------------------------------------------------------------
# CaptureConfig: 正常系
# ---------------------------------------------------------------------------


def _valid_config_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        name="my-book",
        pages=10,
        direction=Direction.RTL,
        wait=1.0,
        out=Path("output"),
        keep_png=True,
    )
    base.update(overrides)
    return base


def test_config_constructs_with_valid_values() -> None:
    c = CaptureConfig(**_valid_config_kwargs())
    assert c.name == "my-book"
    assert c.pages == 10
    assert c.direction is Direction.RTL


# ---------------------------------------------------------------------------
# CaptureConfig: pages 境界値
# ---------------------------------------------------------------------------


def test_config_pages_one_is_minimum_valid() -> None:
    c = CaptureConfig(**_valid_config_kwargs(pages=1))
    assert c.pages == 1


def test_config_pages_zero_rejected() -> None:
    with pytest.raises(ValueError, match="pages"):
        CaptureConfig(**_valid_config_kwargs(pages=0))


def test_config_pages_negative_rejected() -> None:
    with pytest.raises(ValueError, match="pages"):
        CaptureConfig(**_valid_config_kwargs(pages=-3))


def test_config_pages_large_value_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(pages=100000))
    assert c.pages == 100000


# ---------------------------------------------------------------------------
# CaptureConfig: wait 境界値
# ---------------------------------------------------------------------------


def test_config_wait_zero_allowed() -> None:
    c = CaptureConfig(**_valid_config_kwargs(wait=0))
    assert c.wait == 0


def test_config_wait_negative_rejected() -> None:
    with pytest.raises(ValueError, match="wait"):
        CaptureConfig(**_valid_config_kwargs(wait=-0.5))


def test_config_wait_very_small_positive_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(wait=0.001))
    assert c.wait == 0.001


def test_config_wait_large_value_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(wait=300.0))
    assert c.wait == 300.0


# ---------------------------------------------------------------------------
# CaptureConfig: name 境界値
# ---------------------------------------------------------------------------


def test_config_empty_name_rejected() -> None:
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name=""))


def test_config_slash_in_name_rejected() -> None:
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name="path/with/slash"))


def test_config_dot_name_rejected() -> None:
    """'.' は現在ディレクトリを指すので使わせない"""
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name="."))


def test_config_double_dot_name_rejected() -> None:
    """'..' は親ディレクトリを指すのでディレクトリトラバーサルになる"""
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name=".."))


def test_config_null_byte_in_name_rejected() -> None:
    """ヌル文字を含む名前はファイルシステムに対する攻撃ベクタになりうる"""
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name="bad\x00name"))


def test_config_japanese_name_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(name="本のタイトル"))
    assert c.name == "本のタイトル"


def test_config_name_with_space_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(name="my book"))
    assert c.name == "my book"


def test_config_name_with_dot_in_middle_accepted() -> None:
    """ファイル名拡張子のような形式は許容（v1.2 みたいな名前）"""
    c = CaptureConfig(**_valid_config_kwargs(name="book.v1"))
    assert c.name == "book.v1"


def test_config_name_with_hyphen_and_underscore_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(name="my-book_2"))
    assert c.name == "my-book_2"


# ---------------------------------------------------------------------------
# CaptureConfig: 不変性とハッシュ可能性
# ---------------------------------------------------------------------------


def test_config_is_frozen() -> None:
    c = CaptureConfig(**_valid_config_kwargs())
    with pytest.raises(Exception):
        c.pages = 99  # type: ignore[misc]


def test_config_equality_by_value() -> None:
    c1 = CaptureConfig(**_valid_config_kwargs())
    c2 = CaptureConfig(**_valid_config_kwargs())
    assert c1 == c2


def test_config_direction_none_allowed() -> None:
    """auto-direction 経路で direction が確定するまで None を保持できる。"""
    c = CaptureConfig(**_valid_config_kwargs(direction=None))
    assert c.direction is None


# ---------------------------------------------------------------------------
# CaptureConfig: pdf_jpeg_quality 境界値
# ---------------------------------------------------------------------------


def test_config_pdf_jpeg_quality_default_is_none() -> None:
    """未指定なら現状動作 (lossless PNG embed) を保つ."""
    c = CaptureConfig(**_valid_config_kwargs())
    assert c.pdf_jpeg_quality is None


def test_config_pdf_jpeg_quality_accepts_int() -> None:
    c = CaptureConfig(**_valid_config_kwargs(pdf_jpeg_quality=80))
    assert c.pdf_jpeg_quality == 80


def test_config_pdf_jpeg_quality_boundary_one_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(pdf_jpeg_quality=1))
    assert c.pdf_jpeg_quality == 1


def test_config_pdf_jpeg_quality_boundary_hundred_accepted() -> None:
    c = CaptureConfig(**_valid_config_kwargs(pdf_jpeg_quality=100))
    assert c.pdf_jpeg_quality == 100


def test_config_pdf_jpeg_quality_zero_rejected() -> None:
    with pytest.raises(ValueError, match="pdf_jpeg_quality"):
        CaptureConfig(**_valid_config_kwargs(pdf_jpeg_quality=0))


def test_config_pdf_jpeg_quality_one_oh_one_rejected() -> None:
    with pytest.raises(ValueError, match="pdf_jpeg_quality"):
        CaptureConfig(**_valid_config_kwargs(pdf_jpeg_quality=101))


def test_config_pdf_jpeg_quality_negative_rejected() -> None:
    with pytest.raises(ValueError, match="pdf_jpeg_quality"):
        CaptureConfig(**_valid_config_kwargs(pdf_jpeg_quality=-1))
