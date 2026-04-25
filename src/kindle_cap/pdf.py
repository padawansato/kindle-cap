"""Combine PNG images into a single PDF using img2pdf (lossless)."""
from pathlib import Path

import img2pdf


def build_pdf(png_paths: list[Path], out_path: Path) -> None:
    if not png_paths:
        raise ValueError("png_paths must not be empty")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = img2pdf.convert([str(p) for p in png_paths])
    out_path.write_bytes(pdf_bytes)
