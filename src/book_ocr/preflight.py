"""book-ocr のディスク容量 preflight チェック (issue #48).

OCR 実行前に出力ディレクトリと tempdir 双方の残量を確認し、yomitoku が
中間 jpg を吐く分も含めて不足なら起動を止める。実 OCR 開始後の途中失敗
(chunk 1 で全部ロス) を予防する。

`kindle_cap/preflight.py` の構造 (PreflightError + checker 関数) を踏襲。
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path


class PreflightError(RuntimeError):
    """ディスク容量不足など、起動前のチェックで検出した障害を表す."""


# yomitoku は入力 PNG を tempdir に symlink/コピーし、内部で中間 jpg を生成する。
# 入力サイズ × 1.5 倍をマージン込みの上限と見積もる。
_TEMPFILE_MARGIN = 1.5


def estimate_required_bytes(pngs: list[Path], chunk_size: int | None) -> int:
    """OCR 中に同時存在し得る一時データのサイズ見積もり (bytes).

    `chunk_size` が指定されていれば 1 chunk 分のみが同時に展開される (issue #36)。
    省略時は全 PNG 分の容量を要求する。
    """
    if not pngs:
        return 0
    target = pngs if chunk_size is None else pngs[:chunk_size]
    total = sum(p.stat().st_size for p in target)
    return int(total * _TEMPFILE_MARGIN)


def _resolve_existing_ancestor(path: Path) -> Path:
    """指定パスがまだ存在しない場合、最初に存在する祖先まで遡る."""
    probe = path
    while not probe.exists():
        if probe.parent == probe:
            return probe
        probe = probe.parent
    return probe


def check_disk_space(
    *,
    pngs: list[Path],
    out_dir: Path,
    chunk_size: int | None,
    tempdir: Path | None = None,
    disk_usage_fn: Callable[[Path], shutil._ntuple_diskusage] = shutil.disk_usage,
) -> None:
    """out_dir と tempdir 双方のマウントで残量チェック。不足なら PreflightError.

    tempdir を省略時は `tempfile.gettempdir()` を使う。同一マウントなら
    重複チェックは省略する (st_dev で判定)。
    """
    required = estimate_required_bytes(pngs, chunk_size)
    if required == 0:
        return

    tmp = tempdir or Path(tempfile.gettempdir())
    seen_devices: set[int] = set()
    for target in (out_dir, tmp):
        probe = _resolve_existing_ancestor(target)
        try:
            device_id = probe.stat().st_dev
        except OSError:
            continue
        if device_id in seen_devices:
            continue
        seen_devices.add(device_id)
        try:
            usage = disk_usage_fn(probe)
        except OSError:
            continue
        if usage.free < required:
            raise PreflightError(
                f"ディスク容量不足: {target} を含むパーティションに "
                f"約 {required / 1024 / 1024:.0f} MB 必要ですが "
                f"残り {usage.free / 1024 / 1024:.0f} MB しかありません "
                f"({len(pngs)} ページ × {_TEMPFILE_MARGIN} マージン、chunk_size={chunk_size})。"
                " 容量を確保するか `--ignore-disk-check` でバイパスしてください。"
            )
