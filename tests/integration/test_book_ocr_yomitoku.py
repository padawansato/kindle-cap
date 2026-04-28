"""YomiTokuEngine の live integration test (実 OCR 実行).

@pytest.mark.live_ocr で gating。CI ではスキップ。ローカルで
experiments/ocr-poc/.venv-yomitoku/bin/yomitoku が存在し、サンプル PNG が
experiments/ocr-poc/samples-vertical/ にある場合のみ実行される。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from book_ocr.engines.yomitoku import YomiTokuEngine
from book_ocr.protocols import OCREngine

REPO_ROOT = Path(__file__).resolve().parents[2]
_POC_VENV_BIN = REPO_ROOT / "experiments" / "ocr-poc" / ".venv-yomitoku" / "bin" / "yomitoku"
_SAMPLE_PNG = REPO_ROOT / "experiments" / "ocr-poc" / "samples-vertical" / "page_001.png"


pytestmark = pytest.mark.live_ocr


def test_engine_satisfies_protocol() -> None:
    engine = YomiTokuEngine()
    assert isinstance(engine, OCREngine)


def test_run_batch_single_page(tmp_path: Path) -> None:
    if not _POC_VENV_BIN.exists():
        pytest.skip(f"{_POC_VENV_BIN} not found (run yomitoku PoC first)")
    if not _SAMPLE_PNG.exists():
        pytest.skip(f"sample PNG {_SAMPLE_PNG} not found")

    target = tmp_path / "page_001.png"
    shutil.copy(_SAMPLE_PNG, target)

    engine = YomiTokuEngine(device="mps", yomitoku_bin=_POC_VENV_BIN)
    pages = engine.run_batch([target])

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].ocr_engine == "yomitoku"
    assert pages[0].markdown.strip() != ""


def test_run_batch_empty_returns_empty_list() -> None:
    """空入力では subprocess を呼ばずに空リストを返す."""
    engine = YomiTokuEngine()
    assert engine.run_batch([]) == []


def test_resolve_binary_raises_when_missing(tmp_path: Path) -> None:
    bad_path = tmp_path / "does-not-exist"
    engine = YomiTokuEngine(yomitoku_bin=bad_path)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        engine.run_batch([Path("/tmp/page_001.png")])
