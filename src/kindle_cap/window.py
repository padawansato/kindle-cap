"""Activate the Kindle app and read its window geometry via AppleScript."""

import logging
import subprocess

from .config import Geometry

logger = logging.getLogger(__name__)

_ACTIVATE_SCRIPT = 'tell application "Amazon Kindle" to activate'

_GEOMETRY_SCRIPT = """tell application "System Events" to tell process "Kindle"
  set w to window 1
  set pos to position of w
  set sz to size of w
  return ((item 1 of pos) as string) & linefeed & ((item 2 of pos) as string) & linefeed & ((item 1 of sz) as string) & linefeed & ((item 2 of sz) as string)
end tell"""


class WindowGeometryError(RuntimeError):
    """`get_window_geometry` 失敗（osascript exit 非 0 / stdout 解析失敗）。"""


class KindleActivationError(RuntimeError):
    """`activate_kindle` 失敗（osascript exit 非 0）。"""


def _parse_geometry_output(stdout: str) -> Geometry:
    if stdout.strip() == "":
        raise WindowGeometryError(f"unexpected geometry output: {stdout!r}")
    parts = stdout.strip().split("\n")
    if len(parts) != 4:
        raise WindowGeometryError(f"unexpected geometry output: {stdout!r}")
    try:
        x, y, w, h = (int(p.strip()) for p in parts)
    except ValueError as e:
        raise WindowGeometryError(f"could not parse geometry output: {stdout!r}") from e
    return Geometry(x=x, y=y, width=w, height=h)


def _stderr_text(stderr: str | None) -> str:
    return (stderr or "").strip() or "(no stderr)"


def activate_kindle() -> None:
    logger.debug("activating Amazon Kindle via osascript")
    try:
        subprocess.run(
            ["osascript", "-e", _ACTIVATE_SCRIPT],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        text = _stderr_text(e.stderr)
        logger.error("Kindle activation failed (exit %d): %s", e.returncode, text)
        raise KindleActivationError(
            f"osascript activate failed (exit {e.returncode}): {text}"
        ) from e


def get_window_geometry() -> Geometry:
    logger.debug("running osascript geometry probe")
    try:
        result = subprocess.run(
            ["osascript", "-e", _GEOMETRY_SCRIPT],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        text = _stderr_text(e.stderr)
        logger.error("geometry osascript failed (exit %d): %s", e.returncode, text)
        raise WindowGeometryError(
            f"osascript geometry probe failed (exit {e.returncode}): {text}"
        ) from e
    logger.debug("geometry stdout: %r", result.stdout)
    return _parse_geometry_output(result.stdout)
