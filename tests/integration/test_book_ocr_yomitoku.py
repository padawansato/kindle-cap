"""YomiTokuEngine の live integration test (実 OCR 実行).

@pytest.mark.live_ocr で gating。CI ではスキップ。ローカルで
experiments/ocr-poc/.venv-yomitoku/bin/yomitoku が存在し、サンプル PNG が
experiments/ocr-poc/samples-vertical/ にある場合のみ実行される。

live_ocr 不要なユニットテストは tests/unit/test_book_ocr_engine.py にある (issue #22)。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from book_ocr.engines.yomitoku import YomiTokuEngine, extract_figure_refs

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


def test_run_batch_persists_raw_json(tmp_path: Path) -> None:
    """issue #70: OCR の正準形は JSON。md はそこから worker が起こす。

    md レンダ worker が実際に起動できること (yomitoku の import が engine 本体の
    `yomitoku.py` にシャドーされないこと) も、この経路で初めて検証できる。
    """
    if not _POC_VENV_BIN.exists():
        pytest.skip(f"{_POC_VENV_BIN} not found (run yomitoku PoC first)")
    if not _SAMPLE_PNG.exists():
        pytest.skip(f"sample PNG {_SAMPLE_PNG} not found")

    target = tmp_path / "page_001.png"
    shutil.copy(_SAMPLE_PNG, target)
    json_out = tmp_path / "pages"

    engine = YomiTokuEngine(
        device="mps",
        yomitoku_bin=_POC_VENV_BIN,
        json_out_dir=json_out,
        figure_out_dir=tmp_path / "figures",
    )
    (page,) = engine.run_batch([target])

    assert page.json_path == json_out / "page_001.json"
    assert page.json_path is not None and page.json_path.exists()

    raw = json.loads(page.json_path.read_text(encoding="utf-8"))
    # searchable PDF (PR2) が要求するキー。words には座標と縦横の向きが入る。
    assert {"words", "paragraphs", "figures", "tables"} <= raw.keys()
    assert raw["words"], "words が空だと透明テキスト層を作れない"
    assert {"content", "points", "direction"} <= raw["words"][0].keys()


def test_markdown_has_no_raw_yomitoku_figure_attrs(tmp_path: Path) -> None:
    """worker の生出力に残る width / <br> が最終 md に漏れていないこと。

    `convert_markdown` は `<img src="figures/X" width="200px"><br>` を出すが、
    現行 (v0.4.0 まで) の出力は `<img src="figures/X" alt="図">` なので、
    `_finalize_figure_refs` を通した形でなければ book-epub 側の想定と食い違う。
    """
    if not _POC_VENV_BIN.exists():
        pytest.skip(f"{_POC_VENV_BIN} not found (run yomitoku PoC first)")
    if not _SAMPLE_PNG.exists():
        pytest.skip(f"sample PNG {_SAMPLE_PNG} not found")

    target = tmp_path / "page_001.png"
    shutil.copy(_SAMPLE_PNG, target)

    engine = YomiTokuEngine(
        device="mps", yomitoku_bin=_POC_VENV_BIN, figure_out_dir=tmp_path / "figures"
    )
    (page,) = engine.run_batch([target])

    for ref in extract_figure_refs(page.markdown):
        assert (tmp_path / "figures" / ref).exists(), f"{ref} の実体が無い"
    assert 'width="200px"' not in page.markdown
    if extract_figure_refs(page.markdown):
        assert 'alt="図"' in page.markdown
