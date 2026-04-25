"""Validate prerequisites before starting the capture loop."""
import subprocess


class PreflightError(RuntimeError):
    pass


_COUNT_KINDLE_PROC = (
    'tell application "System Events" to '
    '(count (every process whose name is "Kindle"))'
)
_COUNT_KINDLE_WINDOWS = (
    'tell application "System Events" to '
    'tell process "Kindle" to (count windows)'
)
_ACCESSIBILITY_PROBE = (
    'tell application "System Events" to get name of first process'
)


def _run_oscript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _is_kindle_running() -> bool:
    return int(_run_oscript(_COUNT_KINDLE_PROC)) > 0


def _has_kindle_window() -> bool:
    return int(_run_oscript(_COUNT_KINDLE_WINDOWS)) > 0


def _can_send_keystrokes() -> bool:
    try:
        _run_oscript(_ACCESSIBILITY_PROBE)
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if "-1719" in stderr or "not allowed assistive access" in stderr:
            return False
        raise


def preflight() -> None:
    if not _is_kindle_running():
        raise PreflightError(
            "Kindle.app を起動してください（プロセスが見つかりません）"
        )
    if not _has_kindle_window():
        raise PreflightError("Kindle のウィンドウが開いていません")
    if not _can_send_keystrokes():
        raise PreflightError(
            "アクセシビリティ権限が付与されていません。\n"
            "システム設定 > プライバシーとセキュリティ > アクセシビリティ で\n"
            "ターミナル（iTerm2 等）に許可を与えてください。"
        )
