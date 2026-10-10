"""Amazon Kindle.app をアクセシビリティ API (PyObjC) で触る薄い層.

ここにはロジックを置かない。`library` / `reader` / `batch` はこの層の関数を
callable として受け取るので、テストでは偽物に差し替えられる。

実測 (2026-10, Kindle 7.68):
- `osascript` 経由だと要素あたり ~100ms で 32 冊の列挙に 21 秒かかるが、
  `AXUIElementCopyAttributeValue` を直接呼べば 0.07 秒。
- リーダーのツールバー (chrome) はマウスを掃くと出て、Escape で隠れる。
- Cmd+W はアプリごと終了するので使わない。
- 任意の位置へは chrome の「その他のオプション」→「次の位置No.に移動:」で
  ダイアログを出し、「位置No.」の AXTextField に AXValue を入れて「移動」を押す。
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from typing import Any

import Quartz
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    AXValueGetValue,
    kAXChildrenAttribute,
    kAXDescriptionAttribute,
    kAXPositionAttribute,
    kAXRoleAttribute,
    kAXSizeAttribute,
    kAXValueAttribute,
    kAXValueCGPointType,
    kAXValueCGSizeType,
    kAXWindowsAttribute,
)

logger = logging.getLogger(__name__)

AXElement = Any  # PyObjC の AXUIElementRef (型スタブなし)

_PROCESS_NAME = "Kindle"
_APP_NAME = "Amazon Kindle"
_KEY_ESCAPE = 53


class KindleAXError(RuntimeError):
    """Kindle.app が見つからない / アクセシビリティ権限が無い。"""


def kindle_pid() -> int:
    try:
        out = subprocess.check_output(["pgrep", "-x", _PROCESS_NAME], text=True)
    except subprocess.CalledProcessError as e:
        raise KindleAXError(
            f"{_APP_NAME} が起動していません。`open -a '{_APP_NAME}'` で起動してください"
        ) from e
    return int(out.split()[0])


def ensure_trusted() -> None:
    if not AXIsProcessTrusted():
        raise KindleAXError(
            "アクセシビリティ権限がありません。システム設定 > プライバシーとセキュリティ > "
            "アクセシビリティ でターミナル (または実行元アプリ) を許可してください"
        )


def app_element() -> AXElement:
    ensure_trusted()
    return AXUIElementCreateApplication(kindle_pid())


def attr(el: AXElement, name: str) -> Any:
    err, val = AXUIElementCopyAttributeValue(el, name, None)
    return val if err == 0 else None


def perform(el: AXElement, action: str) -> None:
    err = AXUIElementPerformAction(el, action)
    if err != 0:
        raise KindleAXError(f"AX action {action} failed (err={err})")


def set_value(el: AXElement, text: str) -> None:
    """テキストフィールドに値を入れる (Kindle の「位置No.」欄は AXValue の直接設定が効く、実測)."""
    err = AXUIElementSetAttributeValue(el, kAXValueAttribute, text)
    if err != 0:
        raise KindleAXError(f"AX set value failed (err={err})")


def find(app: AXElement, role: str, pred: Callable[[str], bool]) -> list[AXElement]:
    """最前面ウィンドウから role と description が一致する要素を深さ優先で集める.

    一致した要素の子は掘らない (ライブラリの書籍ボタンは同じ description の
    ボタンを入れ子に持つため)。"""
    windows = attr(app, kAXWindowsAttribute) or []
    if not windows:
        return []
    out: list[AXElement] = []

    def rec(el: AXElement) -> None:
        if attr(el, kAXRoleAttribute) == role and pred(attr(el, kAXDescriptionAttribute) or ""):
            out.append(el)
            return
        for child in attr(el, kAXChildrenAttribute) or []:
            rec(child)

    rec(windows[0])
    return out


def description(el: AXElement) -> str:
    return str(attr(el, kAXDescriptionAttribute) or "")


def value(el: AXElement) -> str | None:
    v = attr(el, kAXValueAttribute)
    return None if v is None else str(v)


def frame(el: AXElement) -> tuple[float, float, float, float] | None:
    """要素の (x, y, w, h) を画面座標で返す (取れなければ None)."""
    pos = attr(el, kAXPositionAttribute)
    size = attr(el, kAXSizeAttribute)
    if pos is None or size is None:
        return None
    ok_p, point = AXValueGetValue(pos, kAXValueCGPointType, None)
    ok_s, sz = AXValueGetValue(size, kAXValueCGSizeType, None)
    if not (ok_p and ok_s):
        return None
    return (float(point.x), float(point.y), float(sz.width), float(sz.height))


def window_frame(app: AXElement) -> tuple[float, float, float, float] | None:
    windows = attr(app, kAXWindowsAttribute) or []
    return frame(windows[0]) if windows else None


def activate() -> None:
    subprocess.run(
        ["osascript", "-e", f'tell application "{_APP_NAME}" to activate'],
        check=True,
        capture_output=True,
    )


def key_code(code: int) -> None:
    subprocess.run(
        [
            "osascript",
            "-e",
            f'tell application "System Events" to tell process "{_PROCESS_NAME}" to key code {code}',
        ],
        check=True,
        capture_output=True,
    )


def press_escape() -> None:
    key_code(_KEY_ESCAPE)


def _mouse_move(x: float, y: float) -> None:
    ev = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventMouseMoved, Quartz.CGPointMake(x, y), 0
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def park_mouse(x0: int, y0: int, width: int, height: int) -> None:
    """マウスをページ中央に戻す。ツールバー帯に残したままだと activate のたびに
    chrome が出て撮影に写り込む (実測)。"""
    _mouse_move(x0 + width // 2, y0 + height // 2)
    time.sleep(0.2)


def sweep_mouse(x0: int, y0: int, width: int, height: int) -> None:
    """ウィンドウ内でマウスを掃いてリーダーの chrome を出す (実測で唯一安定した方法)."""
    cx = x0 + width // 2
    cy = y0 + height // 2
    top = y0 + 40  # ツールバー帯。ここまで上げないと chrome が出ない (実測)
    for i in range(30):
        _mouse_move(x0 + width * 0.2 + i * width * 0.02, cy + (i % 5) * 10)
        time.sleep(0.02)
    for i in range(20):
        _mouse_move(cx, cy - (cy - top) * i / 19)
        time.sleep(0.02)
    time.sleep(0.6)
