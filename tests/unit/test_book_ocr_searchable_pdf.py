"""book_ocr.exporters.searchable_pdf のテスト (issue #70).

yomitoku には依存しない。yomitoku `-f json` と同じ形の合成 JSON と白紙 PNG から
PDF を組み、PyMuPDF でテキスト抽出して「コピー・検索できる PDF」になっているかを
E2E で確かめる。標準実装 (create_searchable_pdf) の欠陥 3 点 — 語の欠落・全角化・
縦書きの 1 文字分断 — の回帰テストを兼ねる。
"""

from __future__ import annotations

import errno
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pymupdf
import pytest
from PIL import Image

from book_ocr.exporters.searchable_pdf import (
    SearchablePdfError,
    build_image_pdf,
    order_words,
    overlay_text_layer,
)

PNG_W, PNG_H = 800, 600


def _word(text: str, x0: int, y0: int, x1: int, y1: int, direction: str = "horizontal") -> dict:
    return {
        "content": text,
        "direction": direction,
        "points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
    }


def _para(box: list[int], order: int) -> dict:
    return {"box": box, "order": order}


# 横書き段落 2 つ + 縦書き段落 1 つ + 図内段落 + 表 + どこにも属さない語。
# JSON 内の語の並びはわざと読み順と違えてある。
PAGE_JSON: dict[str, Any] = {
    "paragraphs": [
        _para([40, 200, 420, 300], order=3),
        _para([40, 40, 420, 160], order=2),
        _para([600, 40, 700, 350], order=4),
    ],
    "figures": [{"box": [40, 400, 300, 500], "order": 0, "paragraphs": [_para([40, 400, 300, 500], order=0)]}],
    "tables": [{"box": [320, 400, 560, 500], "order": 1}],
    "words": [
        _word("深い眠り", 40, 250, 200, 290),
        _word("大人に必要な睡眠時間は一般的", 40, 200, 420, 240),
        _word("寝起きが悪い", 240, 40, 420, 80),
        _word("6時半に起き", 40, 40, 220, 80),
        _word("に7〜9時間", 40, 100, 220, 140),
        _word("眠りの深さ", 660, 60, 700, 300, direction="vertical"),
        _word("ノンレム睡眠", 600, 60, 640, 340, direction="vertical"),
        _word("表内", 320, 400, 560, 500),
        _word("図内", 40, 400, 300, 500),
        _word("270分", 500, 550, 580, 590),  # どの段落にも属さない (標準実装が落とす語)
        _word("", 10, 10, 20, 20),
    ],
}
READING_ORDER = [
    "図内",
    "表内",
    "6時半に起き",
    "寝起きが悪い",
    "に7〜9時間",
    "大人に必要な睡眠時間は一般的",
    "深い眠り",
    "眠りの深さ",
    "ノンレム睡眠",
    "270分",
]


@pytest.fixture
def image_pdf(tmp_path: Path) -> Path:
    pngs = []
    for i in (1, 2, 3):
        Image.new("RGB", (PNG_W, PNG_H), "white").save(tmp_path / f"page_{i:03d}.png")
        pngs.append(tmp_path / f"page_{i:03d}.png")
    out = tmp_path / "book.pdf"
    build_image_pdf(pngs, out)
    return out


@pytest.fixture
def page_json(tmp_path: Path) -> Path:
    path = tmp_path / "page_002.json"
    path.write_text(json.dumps(PAGE_JSON, ensure_ascii=False), encoding="utf-8")
    return path


def test_order_words_keeps_every_word_in_reading_order() -> None:
    """コンテナ (段落 / 図内段落 / 表) の order → 横書きは上→下・左→右、縦書きは
    右→左。属さない語も落とさず末尾に。空文字だけ除く。"""
    assert [w.text for w in order_words(PAGE_JSON)] == READING_ORDER


def test_build_image_pdf_matches_kindle_cap_scale(tmp_path: Path, image_pdf: Path) -> None:
    """kindle-cap/img2pdf と同じ 96 dpi (1px = 0.75pt)。overlay の px→pt 変換の前提。"""
    doc = pymupdf.open(image_pdf)
    assert len(doc) == 3
    assert (doc[0].rect.width, doc[0].rect.height) == (PNG_W * 0.75, PNG_H * 0.75)


def test_overlay_makes_every_word_copyable(tmp_path: Path, image_pdf: Path, page_json: Path) -> None:
    out = tmp_path / "book.searchable.pdf"
    result = overlay_text_layer(image_pdf, out, {2: page_json})
    assert (result.pages_written, result.words_written) == (1, 10)

    doc = pymupdf.open(out)
    text = doc[1].get_text()
    # 全語が読み順で抽出できる
    positions = [text.index(w) for w in READING_ORDER]
    assert positions == sorted(positions)
    # 全角化しない (「6時半」→「６時半」)、「〜」(U+301C) を「～」(U+FF5E) に化かさない
    assert "６時半" not in text and "7～9時間" not in text
    # JSON の無いページはそのまま
    assert doc[0].get_text() == "" and doc[2].get_text() == ""
    # 不可視 (render_mode=3): ラスタライズしても白紙
    assert all(v == 255 for v in doc[1].get_pixmap(dpi=36).samples)
    # フォントは subset 埋め込み (Droid Sans Fallback 全体 1.7MB を載せない)
    assert out.stat().st_size - image_pdf.stat().st_size < 200 * 1024


def test_overlay_places_words_on_their_boxes(tmp_path: Path, image_pdf: Path, page_json: Path) -> None:
    """抽出した語の矩形が JSON の bbox (px→pt) に重なる。ずれると選択範囲が本文からずれる。
    同じ行で隣接する語は抽出時に 1 語に連結されるので、部分文字列で引く。"""
    out = tmp_path / "book.searchable.pdf"
    overlay_text_layer(image_pdf, out, {2: page_json})
    page = pymupdf.open(out)[1]
    scale = page.rect.width / PNG_W
    got = [(w[4], pymupdf.Rect(w[:4])) for w in page.get_text("words")]
    for want in order_words(PAGE_JSON):
        rect = next(r for t, r in got if want.text in t)
        x0, y0, x1, y1 = (v * scale for v in want.bbox)
        tol = 0.3 * ((x1 - x0) if want.vertical else (y1 - y0))
        assert rect.x0 < x0 + tol and rect.x1 > x1 - tol, (want.text, rect)
        assert rect.y0 < y0 + tol and rect.y1 > y1 - tol, (want.text, rect)
        assert rect.width < 5 * (x1 - x0) and rect.height < 5 * (y1 - y0), (want.text, rect)


def test_overlay_rejects_pages_beyond_pdf_before_writing(
    tmp_path: Path, image_pdf: Path, page_json: Path
) -> None:
    out = tmp_path / "book.searchable.pdf"
    with pytest.raises(SearchablePdfError, match=r"\[4, 9\]"):
        overlay_text_layer(image_pdf, out, {2: page_json, 4: page_json, 9: page_json})
    assert not out.exists()


def test_overlay_removes_partial_output_on_enospc(
    tmp_path: Path, image_pdf: Path, page_json: Path
) -> None:
    out = tmp_path / "book.searchable.pdf"
    out.write_bytes(b"partial")

    def boom(*_: Any, **__: Any) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    with patch("pymupdf.Document.save", boom), pytest.raises(SearchablePdfError, match="ディスク容量"):
        overlay_text_layer(image_pdf, out, {2: page_json})
    assert not out.exists()
