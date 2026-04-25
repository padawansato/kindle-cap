"""window.py の live integration: 実 osascript を叩いて挙動を検証する。

実行: `uv run pytest -m live tests/integration/test_real_window.py -v`
前提: Kindle.app が起動し、書籍ウィンドウが 1 枚以上開いている

【マルチディスプレイ対応の手動確認】
- Kindle ウィンドウを外部ディスプレイにドラッグ移動して同じテストを実行
- `test_real_get_window_geometry_returns_valid_geometry` が pass することで
  外部ディスプレイの座標範囲（負値や大きな x 値）も正しく取得できていることを実証
"""
import pytest

from kindle_cap.config import Geometry
from kindle_cap.window import activate_kindle, get_window_geometry


@pytest.mark.live
def test_real_activate_kindle_runs_without_error() -> None:
    activate_kindle()  # 例外が出ないこと


@pytest.mark.live
def test_real_get_window_geometry_returns_valid_geometry() -> None:
    geom = get_window_geometry()
    assert isinstance(geom, Geometry)
    # ウィンドウサイズは現実的に小さくない
    assert geom.width >= 200
    assert geom.height >= 200
    # 画面範囲を大きく超える値は異常（複数モニタを考えても 20000 を超えることはない）
    assert -10000 < geom.x < 20000
    assert -10000 < geom.y < 20000
    assert geom.width < 20000
    assert geom.height < 20000


@pytest.mark.live
def test_real_get_window_geometry_is_idempotent() -> None:
    """ウィンドウを動かさない限り、同じ Geometry が返る"""
    g1 = get_window_geometry()
    g2 = get_window_geometry()
    assert g1 == g2
