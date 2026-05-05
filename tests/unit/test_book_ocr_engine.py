"""YomiTokuEngine の live_ocr 不要なユニットテスト.

`tests/integration/test_book_ocr_yomitoku.py` から、yomitoku バイナリを呼ばずに
完結するテストを移動 (issue #22)。

chunked execution テスト (issue #36) は `subprocess.run` を mock して
yomitoku が出力するであろう .md ファイルをシミュレートし、subprocess 呼び出し
回数とページ統合結果を検証する。
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from book_ocr.engines.yomitoku import YomiTokuEngine


def _fake_yomitoku_subprocess(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """yomitoku 出力を模倣: cmd 引数から input/output ディレクトリを取り、
    入力 PNG ごとに `input_<stem>_p1.md` を output_dir に書き出す。"""
    input_dir = Path(cmd[1])
    out_idx = cmd.index("-o")
    output_dir = Path(cmd[out_idx + 1])
    output_dir.mkdir(parents=True, exist_ok=True)
    for png in sorted(input_dir.iterdir()):
        if png.suffix == ".png":
            md = output_dir / f"input_{png.stem}_p1.md"
            md.write_text(f"OCR of {png.name}", encoding="utf-8")
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


def _make_pngs(tmp_path: Path, count: int) -> list[Path]:
    """`page_001.png` 〜 `page_NNN.png` を空ファイルで作成して返す。"""
    pngs: list[Path] = []
    for i in range(1, count + 1):
        p = tmp_path / f"page_{i:03d}.png"
        p.touch()
        pngs.append(p)
    return pngs


def _fake_binary(tmp_path: Path) -> Path:
    """exists() を満たすダミー yomitoku バイナリ。"""
    bin_path = tmp_path / "fake-yomitoku"
    bin_path.touch()
    return bin_path


def test_engine_satisfies_protocol_via_duck_typing() -> None:
    """Protocol 適合は静的型 (mypy) で担保。実行時は名と run_batch の存在で確認."""
    engine = YomiTokuEngine()
    assert hasattr(engine, "name")
    assert isinstance(engine.name, str)
    assert callable(engine.run_batch)


def test_run_batch_empty_returns_empty_list() -> None:
    """空入力では subprocess を呼ばずに空リストを返す."""
    engine = YomiTokuEngine()
    assert engine.run_batch([]) == []


def test_resolve_binary_raises_when_missing(tmp_path: Path) -> None:
    bad_path = tmp_path / "does-not-exist"
    engine = YomiTokuEngine(yomitoku_bin=bad_path)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        engine.run_batch([Path("/tmp/page_001.png")])


# ---------------------------------------------------------------------------
# chunked execution (issue #36)
# ---------------------------------------------------------------------------


@patch("book_ocr.engines.yomitoku.subprocess.run", side_effect=_fake_yomitoku_subprocess)
def test_chunk_size_none_uses_single_subprocess_call(mock_run: MagicMock, tmp_path: Path) -> None:
    """default (chunk_size=None) では従来通り 1 回の subprocess.run。"""
    pngs = _make_pngs(tmp_path, 5)
    engine = YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path))

    pages = engine.run_batch(pngs)

    assert mock_run.call_count == 1
    assert len(pages) == 5
    assert [p.page_number for p in pages] == [1, 2, 3, 4, 5]


@patch("book_ocr.engines.yomitoku.subprocess.run", side_effect=_fake_yomitoku_subprocess)
def test_chunk_size_larger_than_pngs_uses_single_subprocess_call(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    """chunk_size >= len(pngs) は分割不要なので 1 回の呼び出し。"""
    pngs = _make_pngs(tmp_path, 3)
    engine = YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=10)

    pages = engine.run_batch(pngs)

    assert mock_run.call_count == 1
    assert len(pages) == 3


@patch("book_ocr.engines.yomitoku.subprocess.run", side_effect=_fake_yomitoku_subprocess)
def test_chunk_size_splits_into_multiple_subprocess_calls(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    """5 ページ + chunk_size=2 → 3 回の subprocess.run (2+2+1)。"""
    pngs = _make_pngs(tmp_path, 5)
    engine = YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=2)

    pages = engine.run_batch(pngs)

    assert mock_run.call_count == 3
    assert len(pages) == 5
    assert [p.page_number for p in pages] == [1, 2, 3, 4, 5]


@patch("book_ocr.engines.yomitoku.subprocess.run", side_effect=_fake_yomitoku_subprocess)
def test_chunk_size_exact_multiple_of_pngs(mock_run: MagicMock, tmp_path: Path) -> None:
    """6 ページ + chunk_size=3 → 2 回の subprocess.run (3+3)。"""
    pngs = _make_pngs(tmp_path, 6)
    engine = YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=3)

    pages = engine.run_batch(pngs)

    assert mock_run.call_count == 2
    assert [p.page_number for p in pages] == [1, 2, 3, 4, 5, 6]


@patch("book_ocr.engines.yomitoku.subprocess.run", side_effect=_fake_yomitoku_subprocess)
def test_chunk_size_uses_separate_tempdirs_per_chunk(mock_run: MagicMock, tmp_path: Path) -> None:
    """各チャンクで別 tempdir を使う (前チャンクの状態に影響されない)。"""
    pngs = _make_pngs(tmp_path, 4)
    engine = YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=2)

    engine.run_batch(pngs)

    # 各 call の input_dir が異なる tempdir 配下であること
    input_dirs: set[str] = set()
    for call in mock_run.call_args_list:
        cmd: list[str] = call.args[0]
        input_dirs.add(cmd[1])
    assert len(input_dirs) == 2  # チャンク数と一致


def test_chunk_size_zero_rejected_at_construction(tmp_path: Path) -> None:
    """chunk_size=0 や負値は受け付けない (silent split bug 防止)。"""
    with pytest.raises(ValueError, match="chunk_size"):
        YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=0)


def test_chunk_size_negative_rejected_at_construction(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=-1)


@patch("book_ocr.engines.yomitoku.subprocess.run")
def test_chunked_execution_propagates_first_chunk_failure(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    """1 回目のチャンクが timeout したら RuntimeError を raise (途中チャンクも例外)。"""
    pngs = _make_pngs(tmp_path, 5)

    def first_call_times_out(cmd: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd, timeout=1.0)

    mock_run.side_effect = first_call_times_out
    engine = YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=2, timeout_sec=1.0)

    with pytest.raises(RuntimeError, match="timeout"):
        engine.run_batch(pngs)


def _make_failure_after_n_calls(n: int) -> Callable[..., subprocess.CompletedProcess[str]]:
    """最初の n 回は成功、(n+1) 回目で TimeoutExpired を raise する side_effect。"""
    counter = {"n": 0}

    def side_effect(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        counter["n"] += 1
        if counter["n"] > n:
            raise subprocess.TimeoutExpired(cmd, timeout=1.0)
        return _fake_yomitoku_subprocess(cmd, **kwargs)

    return side_effect


@patch("book_ocr.engines.yomitoku.subprocess.run")
def test_chunked_execution_propagates_mid_chunk_failure(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    """1 回目のチャンクは成功、2 回目で timeout → 全体として RuntimeError。

    部分結果の保存 (partial recovery) は別 issue (#41 等)。本 PR では fail-fast 方針。
    """
    pngs = _make_pngs(tmp_path, 5)
    mock_run.side_effect = _make_failure_after_n_calls(1)
    engine = YomiTokuEngine(yomitoku_bin=_fake_binary(tmp_path), chunk_size=2, timeout_sec=1.0)

    with pytest.raises(RuntimeError, match="timeout"):
        engine.run_batch(pngs)
    assert mock_run.call_count == 2  # 1 success + 1 fail
