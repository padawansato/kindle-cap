from pathlib import Path

import pytest

from kindle_cap.config import CaptureConfig, Direction, Geometry


def test_direction_string_values():
    assert Direction.RTL == "rtl"
    assert Direction.LTR == "ltr"


def test_geometry_holds_values():
    g = Geometry(x=0, y=31, width=1440, height=869)
    assert g.x == 0
    assert g.y == 31
    assert g.width == 1440
    assert g.height == 869


def test_geometry_is_frozen():
    g = Geometry(x=0, y=0, width=100, height=100)
    with pytest.raises(Exception):
        g.x = 99  # type: ignore[misc]


def _valid_config_kwargs(**overrides):
    base = dict(
        name="my-book",
        pages=10,
        direction=Direction.RTL,
        wait=1.0,
        out=Path("output"),
        keep_png=True,
    )
    base.update(overrides)
    return base


def test_config_constructs_with_valid_values():
    c = CaptureConfig(**_valid_config_kwargs())
    assert c.name == "my-book"
    assert c.pages == 10
    assert c.direction is Direction.RTL


def test_config_pages_zero_rejected():
    with pytest.raises(ValueError, match="pages"):
        CaptureConfig(**_valid_config_kwargs(pages=0))


def test_config_pages_negative_rejected():
    with pytest.raises(ValueError, match="pages"):
        CaptureConfig(**_valid_config_kwargs(pages=-3))


def test_config_wait_negative_rejected():
    with pytest.raises(ValueError, match="wait"):
        CaptureConfig(**_valid_config_kwargs(wait=-0.5))


def test_config_wait_zero_allowed():
    c = CaptureConfig(**_valid_config_kwargs(wait=0))
    assert c.wait == 0


def test_config_empty_name_rejected():
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name=""))


def test_config_slash_in_name_rejected():
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name="path/with/slash"))
