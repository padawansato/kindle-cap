"""Activate the Kindle app and read its window geometry via AppleScript."""
import subprocess

from .config import Geometry

_ACTIVATE_SCRIPT = 'tell application "Amazon Kindle" to activate'

_GEOMETRY_SCRIPT = """tell application "System Events" to tell process "Kindle"
  set w to window 1
  set pos to position of w
  set sz to size of w
  return ((item 1 of pos) as string) & linefeed & ((item 2 of pos) as string) & linefeed & ((item 1 of sz) as string) & linefeed & ((item 2 of sz) as string)
end tell"""


def _parse_geometry_output(stdout: str) -> Geometry:
    if stdout.strip() == "":
        raise RuntimeError(f"unexpected geometry output: {stdout!r}")
    parts = stdout.strip().split("\n")
    if len(parts) != 4:
        raise RuntimeError(f"unexpected geometry output: {stdout!r}")
    try:
        x, y, w, h = (int(p.strip()) for p in parts)
    except ValueError as e:
        raise RuntimeError(f"could not parse geometry output: {stdout!r}") from e
    return Geometry(x=x, y=y, width=w, height=h)


def activate_kindle() -> None:
    subprocess.run(
        ["osascript", "-e", _ACTIVATE_SCRIPT],
        check=True,
    )


def get_window_geometry() -> Geometry:
    result = subprocess.run(
        ["osascript", "-e", _GEOMETRY_SCRIPT],
        check=True,
        capture_output=True,
        text=True,
    )
    return _parse_geometry_output(result.stdout)
