"""Combine PNG images into a single PDF using img2pdf (lossless)."""
from pathlib import Path

import img2pdf


def build_pdf(png_paths: list[Path], out_path: Path) -> None:
    if not png_paths:
        raise ValueError("png_paths must not be empty")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # outputstream を渡すことで、PDF 全体を一度メモリに展開せずに直接ファイルへ
    # 書き出せる。1000+ ページのリフロー型書籍など長尺キャプチャに対応するため
    # ストリーム出力を採用。
    with open(out_path, "wb") as fp:
        img2pdf.convert([str(p) for p in png_paths], outputstream=fp)
