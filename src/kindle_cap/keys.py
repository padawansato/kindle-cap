"""Send arrow-key presses to the Kindle process via System Events."""

import logging
import subprocess

from .config import Direction

logger = logging.getLogger(__name__)

_KEY_RIGHT = 124
_KEY_LEFT = 123


class KeystrokeError(RuntimeError):
    """`send_next_page` 失敗（osascript exit 非 0）。"""


def _key_code_for(direction: Direction) -> int:
    if direction is Direction.RTL:
        return _KEY_RIGHT
    return _KEY_LEFT


def _build_keystroke_script(key_code: int) -> str:
    return f'tell application "System Events" to tell process "Kindle" to key code {key_code}'


def send_next_page(direction: Direction) -> None:
    key_code = _key_code_for(direction)
    script = _build_keystroke_script(key_code)
    logger.debug("sending key code %d (direction=%s)", key_code, direction.value)
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or "").strip() or "(no stderr)"
        logger.error("keystroke osascript failed (exit %d): %s", e.returncode, stderr_text)
        raise KeystrokeError(
            f"osascript keystroke failed (exit {e.returncode}): {stderr_text}"
        ) from e
