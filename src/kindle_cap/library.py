"""Library mode: iterate over books in the Kindle library grid.

Kindle.app のライブラリ画面はカバー画像のグリッドで構成される。本モジュールは
グリッドの各セル中央のスクリーン座標を計算し、System Events 経由でクリック
することで「次の本を開く」自動化を可能にする。
"""
import subprocess

from .config import Geometry


def compute_book_positions(
    window_geom: Geometry,
    n_cols: int = 6,
    top_padding: int = 80,
    bottom_padding: int = 50,
    left_padding: int = 30,
    right_padding: int = 30,
    row_height: int = 240,
) -> list[tuple[int, int]]:
    """ライブラリ画面の各書籍カバーの中央座標を返す。

    Args:
        window_geom: Kindle ウィンドウの位置とサイズ（仮想スクリーン座標系）
        n_cols: 1 行あたりの書籍数（Kindle.app のウィンドウサイズに依存）
        top_padding: タブバー＋フィルタバー分の上端余白
        bottom_padding: 下部タブバー分の下端余白
        left_padding / right_padding: 左右の余白
        row_height: 書籍カバー 1 行分の高さ（カバー縦サイズ + ギャップ）

    Returns:
        画面に表示される全セルの (x, y) リスト。左から右、上から下の順。
    """
    if n_cols <= 0:
        raise ValueError("n_cols must be positive")

    inner_width = window_geom.width - left_padding - right_padding
    if inner_width <= 0:
        raise ValueError("window too narrow for given paddings")

    cell_width = inner_width / n_cols

    inner_height = window_geom.height - top_padding - bottom_padding
    n_rows = max(0, inner_height // row_height)

    positions: list[tuple[int, int]] = []
    for row in range(n_rows):
        for col in range(n_cols):
            x = window_geom.x + left_padding + int(cell_width * (col + 0.5))
            y = window_geom.y + top_padding + int(row_height * (row + 0.5))
            positions.append((x, y))
    return positions


def click_at(x: int, y: int) -> None:
    """指定スクリーン座標を Kindle プロセス内でクリックする。"""
    script = (
        f'tell application "System Events" to tell process "Kindle" '
        f"to click at {{{x}, {y}}}"
    )
    subprocess.run(["osascript", "-e", script], check=True)


def close_book() -> None:
    """Cmd+W で現在の本を閉じてライブラリに戻る。"""
    script = (
        'tell application "System Events" to tell process "Kindle" '
        'to keystroke "w" using command down'
    )
    subprocess.run(["osascript", "-e", script], check=True)


def back_to_library() -> None:
    """Cmd+L でライブラリ画面に戻る（保険）。"""
    script = (
        'tell application "System Events" to tell process "Kindle" '
        'to keystroke "l" using command down'
    )
    subprocess.run(["osascript", "-e", script], check=True)
