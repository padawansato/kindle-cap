from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from kindle_cap.pdf import build_pdf


@pytest.fixture
def sample_pngs(tmp_path: Path) -> list[Path]:
    paths = []
    for i, color in enumerate(["red", "green", "blue"], 1):
        p = tmp_path / f"page_{i:03d}.png"
        Image.new("RGB", (200, 300), color).save(p)
        paths.append(p)
    return paths


def test_build_pdf_creates_pdf_file(sample_pngs: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    build_pdf(sample_pngs, out)
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_build_pdf_has_three_pages(sample_pngs: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    build_pdf(sample_pngs, out)
    reader = PdfReader(str(out))
    assert len(reader.pages) == 3


def test_build_pdf_creates_parent_dirs(sample_pngs: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deep" / "out.pdf"
    build_pdf(sample_pngs, out)
    assert out.exists()


def test_build_pdf_empty_list_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        build_pdf([], tmp_path / "o.pdf")
