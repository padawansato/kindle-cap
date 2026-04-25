"""Send arrow-key presses to the Kindle process via System Events."""

import subprocess

from .config import Direction

_KEY_RIGHT = 124
_KEY_LEFT = 123


def _key_code_for(direction: Direction) -> int:
    if direction is Direction.RTL:
        return _KEY_RIGHT
    return _KEY_LEFT


def _build_keystroke_script(key_code: int) -> str:
    return f'tell application "System Events" to tell process "Kindle" to key code {key_code}'


def send_next_page(direction: Direction) -> None:
    script = _build_keystroke_script(_key_code_for(direction))
    subprocess.run(
        ["osascript", "-e", script],
        check=True,
    )
