"""Combine PNG images into a single PDF using img2pdf (lossless)."""

import errno
from pathlib import Path

import img2pdf


class PdfBuildError(Exception):
    """build_pdf がディスク容量不足など予測可能な要因で失敗したことを表す."""


def build_pdf(png_paths: list[Path], out_path: Path) -> None:
    if not png_paths:
        raise ValueError("png_paths must not be empty")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # outputstream を渡すことで、PDF 全体を一度メモリに展開せずに直接ファイルへ
    # 書き出せる。1000+ ページのリフロー型書籍など長尺キャプチャに対応するため
    # ストリーム出力を採用。
    try:
        with open(out_path, "wb") as fp:
            img2pdf.convert([str(p) for p in png_paths], outputstream=fp)
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
