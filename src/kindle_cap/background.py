"""フォーカスを奪わない撮影バックエンド (issue #84).

`screencapture -R` と `System Events key code` は Kindle が前面にないと使えない。
代わりに窓 ID 指定の `CGWindowListCreateImage` と、pid 宛ての `CGEventPostToPid` を
使うと、Kindle を他の窓の裏に置いたまま撮影とページ送りができる。

実測 (2026-10-11, Kindle 7.68 / macOS 26):
- 他の窓で覆われていても窓の内容は Retina 2x で正しく取れる
- hide (Cmd+H) / minimize すると窓が offscreen になり `CGWindowListCreateImage` は None
- ライブラリ画面の AXPress は前面でないと「選択モード」になるので、本を開く工程は
  前面で行い、撮影ループだけ裏に回す
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import Quartz
from Foundation import NSURL
from PIL import Image

from .capture import _flatten_alpha
from .config import Direction
from .keys import _key_code_for

logger = logging.getLogger(__name__)

_PROCESS_NAME = "Kindle"
_WINDOW_NAME = "Kindle"


class KindleNotRunningError(RuntimeError):
    """Kindle.app のプロセスが見つからない。"""


@dataclass(frozen=True)
class KindleWindow:
    window_id: int
    x: int
    y: int
    width: int
    height: int
    onscreen: bool


def kindle_pid() -> int:
    try:
        out = subprocess.check_output(["pgrep", "-x", _PROCESS_NAME], text=True)
    except subprocess.CalledProcessError as e:
        raise KindleNotRunningError("Amazon Kindle が起動していません") from e
    return int(out.split()[0])


def kindle_window() -> KindleWindow | None:
    """Kindle のメイン窓 (ライブラリとリーダーは同じ窓)。無ければ None。"""
    pid = kindle_pid()
    infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
    for info in infos:
        if info.get("kCGWindowOwnerPID") != pid or info.get("kCGWindowName") != _WINDOW_NAME:
            continue
        b = info["kCGWindowBounds"]
        return KindleWindow(
            window_id=int(info["kCGWindowNumber"]),
            x=int(b["X"]),
            y=int(b["Y"]),
            width=int(b["Width"]),
            height=int(b["Height"]),
            onscreen=bool(info.get("kCGWindowIsOnscreen", False)),
        )
    return None


def _crop_top_px(image_height: int, window_height: int, points: int) -> int:
    """論理ポイントの crop_top を画像ピクセルに換算する (Retina 2x なら 2 倍)。"""
    if points <= 0:
        return 0
    return round(points * image_height / window_height)


def capture_kindle_window(out_path: Path, *, crop_top: int = 0) -> bool:
    """Kindle 窓を前面に出さずに PNG へ撮る。窓が offscreen なら False (撮らない)。

    `crop_top` は `kindle-cap --crop-top` と同じ論理ポイント指定。窓の内容にはタイトルバーが
    含まれるので、固定型書籍で信号機ボタンが写り込む場合に使う (issue #69)。
    """
    win = kindle_window()
    if win is None:
        logger.debug("Kindle の窓が見つかりません")
        return False
    image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        win.window_id,
        Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageBestResolution,
    )
    if image is None:
        logger.debug("CGWindowListCreateImage が None (onscreen=%s)", win.onscreen)
        return False
    dest = Quartz.CGImageDestinationCreateWithURL(
        NSURL.fileURLWithPath_(str(out_path)), "public.png", 1, None
    )
    Quartz.CGImageDestinationAddImage(dest, image, None)
    if not Quartz.CGImageDestinationFinalize(dest):
        logger.error("PNG の書き出しに失敗: %s", out_path)
        return False
    px = _crop_top_px(Quartz.CGImageGetHeight(image), win.height, crop_top)
    if px:
        img = Image.open(out_path)
        img.crop((0, px, img.width, img.height)).save(out_path)
    _flatten_alpha(out_path)
    return True


def post_key(code: int, *, pid: int | None = None) -> None:
    """Kindle の pid 宛てにキーの down/up を送る。Kindle が前面でなくても届く。"""
    target = kindle_pid() if pid is None else pid
    for down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, code, down)
        Quartz.CGEventPostToPid(target, event)


def post_next_page(direction: Direction) -> None:
    code = _key_code_for(direction)
    logger.debug("posting key code %d to Kindle (direction=%s)", code, direction.value)
    post_key(code)
