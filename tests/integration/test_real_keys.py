"""keys.py の live integration: 実 osascript でキーを送り、画面が実際に変わるかを確認。

各テストは net で副作用ゼロになるよう、進めたあと戻すペアで構成。
"""

import hashlib
from pathlib import Path
from time import sleep

import pytest

from kindle_cap.capture import capture_rect
from kindle_cap.config import Direction
from kindle_cap.keys import send_next_page
from kindle_cap.window import activate_kindle, get_window_geometry


def _capture_hash(tmp_path: Path, label: str) -> str:
    activate_kindle()
    geom = get_window_geometry()
    p = tmp_path / f"{label}.png"
    capture_rect(geom, p)
    return hashlib.md5(p.read_bytes()).hexdigest()


@pytest.mark.live
def test_real_send_next_page_changes_screen(tmp_path: Path) -> None:
    """RTL のキーで画面が変わることを確認、検証後に LTR で元に戻す。"""
    h_before = _capture_hash(tmp_path, "before")

    send_next_page(Direction.RTL)
    sleep(1.5)
    h_after = _capture_hash(tmp_path, "after")

    # 画面のピクセルが変わっている = ページが進んだ
    assert h_before != h_after, "右矢印を送ったのに画面が変わっていない"

    # 復元（同じセッションを汚さない）
    send_next_page(Direction.LTR)
    sleep(1.5)


@pytest.mark.live
def test_real_send_left_returns_to_previous_page(tmp_path: Path) -> None:
    """RTL → LTR で同じ画面に戻ることを確認（副作用ゼロ）。

    ※ Kindle の見開きページの制約で完全一致しないケースもあるが、
       多くの本では同じピクセルで戻るはず。
    """
    h_origin = _capture_hash(tmp_path, "origin")

    send_next_page(Direction.RTL)
    sleep(1.5)
    send_next_page(Direction.LTR)
    sleep(1.5)

    h_back = _capture_hash(tmp_path, "back")
    assert h_origin == h_back, "RTL → LTR で同じページに戻らなかった"
