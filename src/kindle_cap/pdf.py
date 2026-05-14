"""Combine PNG images into a single PDF using img2pdf.

`jpeg_quality` 未指定時は PNG を lossless で埋め込む (img2pdf のデフォルト動作)。
指定時は Pillow で各 PNG を JPEG bytes に再圧縮してから埋め込み、PDF サイズを
~1/10 に縮小可能にする (テキスト書籍向けの trade-off オプション)。
"""

import errno
from io import BytesIO
from pathlib import Path

import img2pdf
from PIL import Image


class PdfBuildError(Exception):
    """build_pdf がディスク容量不足など予測可能な要因で失敗したことを表す."""


def _png_to_jpeg_bytes(png_path: Path, quality: int) -> bytes:
    with Image.open(png_path) as img:
        rgb = img.convert("RGB") if img.mode != "RGB" else img
        buf = BytesIO()
        rgb.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()


def build_pdf(
    png_paths: list[Path],
    out_path: Path,
    *,
    jpeg_quality: int | None = None,
) -> None:
    if not png_paths:
        raise ValueError("png_paths must not be empty")
    if jpeg_quality is not None and not (1 <= jpeg_quality <= 100):
        raise ValueError(f"jpeg_quality must be in 1..100 (got {jpeg_quality})")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    inputs: list[str] | list[bytes]
    if jpeg_quality is None:
        inputs = [str(p) for p in png_paths]
    else:
        inputs = [_png_to_jpeg_bytes(p, jpeg_quality) for p in png_paths]

    # outputstream を渡すことで、PDF 全体を一度メモリに展開せずに直接ファイルへ
    # 書き出せる。1000+ ページのリフロー型書籍など長尺キャプチャに対応するため
    # ストリーム出力を採用。
    try:
        with open(out_path, "wb") as fp:
            img2pdf.convert(inputs, outputstream=fp)
    except OSError as e:
        # 中途半端に書かれた PDF は再生成のじゃまになるので削除
        out_path.unlink(missing_ok=True)
        if e.errno == errno.ENOSPC:
            png_dir = png_paths[0].parent
            raise PdfBuildError(
                f"ディスク容量不足で PDF を作成できませんでした。"
                f"PNG は {png_dir} に残っているので、容量を確保後に "
                f"`kindle-cap-pdf {png_dir}` で再生成可能です。"
            ) from e
        raise
