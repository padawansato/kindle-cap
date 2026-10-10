"""既存の画像 PDF に不可視テキスト層を重ねて searchable PDF を作る (issue #70).

入力は yomitoku `-f json` の出力 (`pages/page_NNN.json`) と、kindle-cap が
img2pdf で作った画像のみの PDF。PDF を作り直さず、各ページの上に
`render_mode=3` (塗りも線もなし) で語を描くだけなので、画像の再エンコードが
起きず出力サイズは元 PDF + テキスト層分で済む。

yomitoku 標準の `create_searchable_pdf` を使わない理由:

- `is_contained(container, word, 0.7)` の閾値割れで語の 15〜20% が落ちる
- 縦書きを `to_full_width` で全角化し (「6時半」→「６時半」)、1 文字ずつ描く

ここでは **全 `words[]` をそれぞれの矩形に描く**。`paragraphs` / `figures` /
`tables` は読み順 (テキスト抽出時の並び) の決定にだけ使う。

yomitoku には依存しない (`json` + PyMuPDF のみ) ので CI で unit test できる。
"""

from __future__ import annotations

import errno
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image

# kindle-cap の PNG は 96 dpi 相当で PDF に載る (2940px → 2205pt)。
# build_image_pdf でも同じ縮尺にして、overlay 側の px→pt 変換を共通にする。
_PT_PER_PX = 72 / 96

# PyMuPDF 組み込みの日本語フォント。TextWriter 経由なら「〜」(U+301C) もそのまま
# 抽出できる (page.insert_text 経由だと U+FF5E に化ける)。
_FONT_NAME = "japan"


class SearchablePdfError(Exception):
    """searchable PDF の生成に失敗した (入力不整合・ディスク容量不足など)."""


@dataclass(frozen=True)
class Word:
    text: str
    bbox: tuple[float, float, float, float]  # px、(x0, y0, x1, y1)
    vertical: bool


@dataclass(frozen=True)
class OverlayResult:
    pages_written: int
    words_written: int


# ---------------------------------------------------------------------------
# 読み順 (純粋関数)
# ---------------------------------------------------------------------------


def _bbox(points: Iterable[Sequence[float]]) -> tuple[float, float, float, float]:
    pts = [(float(p[0]), float(p[1])) for p in points]
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _containers(raw: Mapping[str, Any]) -> list[tuple[float, float, float, float]]:
    """読み順に並べたコンテナ矩形。段落 / 図内段落 / 表を共通の `order` で並べる.

    図は `order` を持つが、中の段落も独自の `order` (図内で 0 始まり) を持つので
    (図の order, 図内段落の order) で二段ソートする。"""
    keyed: list[tuple[tuple[float, float], tuple[float, float, float, float]]] = []
    for p in raw.get("paragraphs", []):
        keyed.append(((p["order"], 0), tuple(map(float, p["box"]))))  # type: ignore[arg-type]
    for f in raw.get("figures", []):
        for p in f.get("paragraphs", []):
            keyed.append(((f["order"], p["order"]), tuple(map(float, p["box"]))))  # type: ignore[arg-type]
    for t in raw.get("tables", []):
        keyed.append(((t["order"], 0), tuple(map(float, t["box"]))))  # type: ignore[arg-type]
    keyed.sort(key=lambda kv: kv[0])
    return [box for _, box in keyed]


def order_words(raw: Mapping[str, Any]) -> list[Word]:
    """yomitoku JSON の `words[]` を読み順に並べる。空文字以外は 1 語も落とさない.

    語の中心点を含む最初のコンテナ (段落 / 図内段落 / 表) に所属させ、コンテナの
    `order` 順 → コンテナ内は横書きなら上→下・左→右、縦書きなら右→左・上→下。
    どのコンテナにも属さない語は末尾に、位置順で並べる。"""
    containers = _containers(raw)
    keyed: list[tuple[tuple[float, float, float], Word]] = []
    for w in raw.get("words", []):
        text = w.get("content", "")
        if not text:
            continue
        bbox = _bbox(w["points"])
        vertical = w.get("direction") == "vertical"
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        slot = len(containers)
        for i, (bx0, by0, bx1, by1) in enumerate(containers):
            if bx0 <= cx <= bx1 and by0 <= cy <= by1:
                slot = i
                break
        within = (-x0, y0) if vertical else (y0, x0)
        keyed.append(((slot, *within), Word(text=text, bbox=bbox, vertical=vertical)))
    keyed.sort(key=lambda kv: kv[0])
    return [w for _, w in keyed]


# ---------------------------------------------------------------------------
# PDF 生成
# ---------------------------------------------------------------------------


def build_image_pdf(png_paths: list[Path], out_path: Path) -> None:
    """PNG を 1 ページ 1 枚で束ねた画像 PDF を作る (kindle-cap の PDF が無いときの代替).

    縮尺は kindle-cap/img2pdf 出力と同じ 96 dpi (1px = 0.75pt)。"""
    if not png_paths:
        raise ValueError("png_paths must not be empty")
    doc = pymupdf.open()
    try:
        for png in png_paths:
            pix = pymupdf.Pixmap(str(png))
            page = doc.new_page(width=pix.width * _PT_PER_PX, height=pix.height * _PT_PER_PX)
            page.insert_image(page.rect, pixmap=pix)
        _save(doc, out_path)
    finally:
        doc.close()


def _load_words(json_path: Path) -> list[Word]:
    return order_words(json.loads(json_path.read_text(encoding="utf-8")))


def _png_size_px(png_path: Path) -> tuple[int, int]:
    """OCR にかけた PNG のピクセルサイズ (ヘッダだけ読む)。JSON の座標系はこれ."""
    with Image.open(png_path) as img:
        return int(img.width), int(img.height)


def _draw_words(page: pymupdf.Page, words: list[Word], png_path: Path, font: pymupdf.Font) -> None:
    """語ごとに矩形へ不可視テキストを描く.

    縮尺は PDF ページ寸法 ÷ OCR した PNG のピクセル寸法。PDF 側の画像が JPEG 再圧縮や
    縮小で別解像度になっていても、JSON の座標は PNG 基準なので正しく乗る。
    横書き: 語の幅にフォントサイズを合わせ、基線は下端 + descender。
    縦書き: 列の上端を起点に横書きで組んでから、起点まわりに 90° 回して
    上→下に流す (1 語 = 1 テキストオブジェクトなので抽出時に分断されない)。"""
    img_w, img_h = _png_size_px(png_path)
    sx = page.rect.width / img_w
    sy = page.rect.height / img_h
    for w in words:
        unit = font.text_length(w.text, fontsize=1)
        if unit <= 0:
            continue
        x0, y0, x1, y1 = w.bbox[0] * sx, w.bbox[1] * sy, w.bbox[2] * sx, w.bbox[3] * sy
        tw = pymupdf.TextWriter(page.rect)
        if w.vertical:
            fontsize = (y1 - y0) / unit
            # PyMuPDF は y 下向きなので Matrix(-90) で進行方向 (+x) が下 (+y) に向く。
            # 回転後、基線は x = fx の縦線で、descender は左 (-x)、字面は右 (+x) に出る。
            # fx を x0 から descender 分だけ内側に寄せて列 [x0, x1] に収める。
            fx = x0 - font.descender * fontsize
            origin = pymupdf.Point(fx, y0)
            tw.append(origin, w.text, font=font, fontsize=fontsize)
            tw.write_text(page, render_mode=3, morph=(origin, pymupdf.Matrix(-90)))
        else:
            fontsize = (x1 - x0) / unit
            baseline = y1 + font.descender * fontsize
            tw.append(pymupdf.Point(x0, baseline), w.text, font=font, fontsize=fontsize)
            tw.write_text(page, render_mode=3)


def _save(doc: pymupdf.Document, out_path: Path) -> None:
    """保存。失敗時は書きかけのファイルを消してから SearchablePdfError にする.

    TextWriter は "japan" でも Droid Sans Fallback (1.7MB) を埋め込むので subset にする。"""
    try:
        doc.subset_fonts()
        doc.save(out_path, garbage=1, deflate=True)
    except OSError as e:
        out_path.unlink(missing_ok=True)
        if e.errno == errno.ENOSPC:
            raise SearchablePdfError(f"ディスク容量不足で PDF を書けません: {out_path}") from e
        raise SearchablePdfError(f"PDF を書けません: {out_path}: {e}") from e
    except Exception:
        out_path.unlink(missing_ok=True)
        raise


def overlay_text_layer(
    pdf_in: Path, out_path: Path, pages: Mapping[int, tuple[Path, Path]]
) -> OverlayResult:
    """`pdf_in` の各ページに語を不可視描画して `out_path` に書く.

    `pages` は page_number → (OCR JSON, OCR にかけた PNG)。無いページはそのまま
    (テキスト層なし)。PDF のページ数を超えるページ番号があれば、何も書かずに
    SearchablePdfError で列挙する。"""
    # JSON は PDF を開く前に全部読む (読めなければ部分出力を作らずに落ちる)
    words_by_page = {n: (_load_words(j), png) for n, (j, png) in sorted(pages.items())}
    doc = pymupdf.open(pdf_in)
    try:
        beyond = [n for n in words_by_page if not 1 <= n <= len(doc)]
        if beyond:
            raise SearchablePdfError(
                f"PDF は {len(doc)} ページですが、範囲外のページ番号の JSON があります: {beyond}"
            )
        font = pymupdf.Font(_FONT_NAME)
        pages_written = 0
        words_written = 0
        for n, (words, png) in words_by_page.items():
            if not words:
                continue
            _draw_words(doc[n - 1], words, png, font)
            pages_written += 1
            words_written += len(words)
        _save(doc, out_path)
    finally:
        doc.close()
    return OverlayResult(pages_written=pages_written, words_written=words_written)
