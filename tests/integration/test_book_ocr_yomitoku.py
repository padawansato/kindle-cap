"""YomiTokuEngine の live integration test (実 OCR 実行).

@pytest.mark.live_ocr で gating。CI ではスキップ。ローカルで
experiments/ocr-poc/.venv-yomitoku/bin/yomitoku が存在し、サンプル PNG が
experiments/ocr-poc/samples-vertical/ にある場合のみ実行される。

live_ocr 不要なユニットテストは tests/unit/test_book_ocr_engine.py にある (issue #22)。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from book_ocr.engines.yomitoku import YomiTokuEngine

REPO_ROOT = Path(__file__).resolve().parents[2]
_POC_VENV_BIN = REPO_ROOT / "experiments" / "ocr-poc" / ".venv-yomitoku" / "bin" / "yomitoku"
_SAMPLE_PNG = REPO_ROOT / "experiments" / "ocr-poc" / "samples-vertical" / "page_001.png"


pytestmark = pytest.mark.live_ocr


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
