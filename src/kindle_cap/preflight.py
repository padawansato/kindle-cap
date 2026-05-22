"""Validate prerequisites before starting the capture loop."""

import hashlib
import subprocess
from collections.abc import Callable
from pathlib import Path

from .config import Direction, Geometry


class PreflightError(RuntimeError):
    pass


_COUNT_KINDLE_PROC = (
    'tell application "System Events" to (count (every process whose name is "Kindle"))'
)
_COUNT_KINDLE_WINDOWS = (
    'tell application "System Events" to tell process "Kindle" to (count windows)'
)
_ACCESSIBILITY_PROBE = 'tell application "System Events" to get name of first process'


def _parse_count(stdout: str) -> int:
    return int(stdout.strip())


def _is_accessibility_error(stderr: str | None) -> bool:
    if not stderr:
        return False
    return "-1719" in stderr or "not allowed assistive access" in stderr


def _run_oscript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _is_kindle_running() -> bool:
    return _parse_count(_run_oscript(_COUNT_KINDLE_PROC)) > 0


def _has_kindle_window() -> bool:
    return _parse_count(_run_oscript(_COUNT_KINDLE_WINDOWS)) > 0


def _can_send_keystrokes() -> bool:
    try:
        _run_oscript(_ACCESSIBILITY_PROBE)
        return True
    except subprocess.CalledProcessError as e:
        if _is_accessibility_error(e.stderr):
            return False
        raise


def preflight() -> None:
    if not _is_kindle_running():
        raise PreflightError("Kindle.app を起動してください（プロセスが見つかりません）")
    if not _has_kindle_window():
        raise PreflightError("Kindle のウィンドウが開いていません")
    if not _can_send_keystrokes():
        raise PreflightError(
            "アクセシビリティ権限が付与されていません。\n"
            "システム設定 > プライバシーとセキュリティ > アクセシビリティ で\n"
            "ターミナル（iTerm2 等）に許可を与えてください。"
        )


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def detect_direction(
    *,
    out_dir: Path,
    geom_provider: Callable[[], Geometry],
    activator: Callable[[], None],
    capturer: Callable[[Geometry, Path], None],
    sender: Callable[[Direction], None],
    sleeper: Callable[[float], None],
    wait: float,
    probe_direction: Direction = Direction.RTL,
    probe_count: int = 3,
) -> tuple[Direction, list[Path]]:
    """表紙起点で direction を判定する。

    アルゴリズム:
        1. 起点フレーム（表紙）を page_001.png として撮影
        2. probe_direction を probe_count 回送って page_002..page_{probe_count+1}.png に撮影
        3. 表紙と最終試写を MD5 比較:
           - 変化あり → (probe_direction, [page_001, ..., page_{probe_count+1}]) を返す
              （表紙＋試写を本番採用）
           - 変化なし → 試写を全削除し、逆方向で 1 回だけ verify を page_002.png に撮る
              - verify で変化あり → (other_direction, [page_001, page_002]) を返す
              - verify でも変化なし → page_001 / page_002 を削除して PreflightError

    返り値の list[Path] は常に「最終出力に含めるべき初期ページ群」を意味し、
    先頭が表紙 (page_001.png)、後続が probe direction で進めた後のフレーム。
    呼び出し側 _capture_book に start_index = len(...) + 1 / seed_hashes として渡す。
    """
    activator()
    geom = geom_provider()
    cover_path = out_dir / "page_001.png"
    capturer(geom, cover_path)
    cover_hash = _md5(cover_path)
    keep_cover = False
    try:
        probe_pngs: list[Path] = []
        for i in range(1, probe_count + 1):
            sender(probe_direction)
            sleeper(wait)
            activator()
            geom = geom_provider()
            png = out_dir / f"page_{i + 1:03d}.png"
            capturer(geom, png)
            probe_pngs.append(png)

        if _md5(probe_pngs[-1]) != cover_hash:
            keep_cover = True
            return probe_direction, [cover_path, *probe_pngs]

        # probe 無反応 → 試写を全削除して逆方向で確認
        for p in probe_pngs:
            p.unlink(missing_ok=True)
        other = Direction.LTR if probe_direction is Direction.RTL else Direction.RTL
        sender(other)
        sleeper(wait)
        activator()
        geom = geom_provider()
        verify_path = out_dir / "page_002.png"
        capturer(geom, verify_path)
        if _md5(verify_path) != cover_hash:
            keep_cover = True
            return other, [cover_path, verify_path]
        verify_path.unlink(missing_ok=True)

        raise PreflightError(
            "両方向ともページが進みません。"
            "Kindle にフォーカスがないか、書籍が 1 ページしかない可能性があります。"
        )
    finally:
        if not keep_cover:
            cover_path.unlink(missing_ok=True)
