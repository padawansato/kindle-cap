"""YomiTokuEngine の live_ocr 不要なユニットテスト.

`tests/integration/test_book_ocr_yomitoku.py` から、yomitoku バイナリを呼ばずに
完結するテストを移動 (issue #22)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from book_ocr.engines.yomitoku import YomiTokuEngine


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
