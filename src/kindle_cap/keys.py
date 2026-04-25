"""Send arrow-key presses to the Kindle process via System Events."""
import subprocess

from .config import Direction

_KEY_RIGHT = 124
_KEY_LEFT = 123


def send_next_page(direction: Direction) -> None:
    key_code = _KEY_RIGHT if direction is Direction.RTL else _KEY_LEFT
    script = (
        f'tell application "System Events" to tell process "Kindle" '
        f'to key code {key_code}'
    )
    subprocess.run(
        ["osascript", "-e", script],
        check=True,
    )
