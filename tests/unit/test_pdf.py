import errno
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from PIL import Image
from pypdf import PdfReader

from kindle_cap.pdf import PdfBuildError, build_pdf


@pytest.fixture
def sample_pngs(tmp_path: Path) -> list[Path]:
    paths = []
    for i, color in enumerate(["red", "green", "blue"], 1):
        p = tmp_path / f"page_{i:03d}.png"
        Image.new("RGB", (200, 300), color).save(p)
        paths.append(p)
    return paths


def _make_rgb_png(path: Path, size: tuple[int, int] = (100, 100), color: str = "red") -> Path:
    Image.new("RGB", size, color).save(path)
    return path


# ---------------------------------------------------------------------------
# 基本動作
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 境界値
# ---------------------------------------------------------------------------


def test_build_pdf_rejects_empty_list(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        build_pdf([], tmp_path / "o.pdf")


def test_build_pdf_handles_single_png(tmp_path: Path) -> None:
    """最小有効ページ数: 1 枚"""
    p = _make_rgb_png(tmp_path / "only.png")
    out = tmp_path / "single.pdf"
    build_pdf([p], out)
    assert len(PdfReader(str(out)).pages) == 1


def test_build_pdf_handles_many_pngs(tmp_path: Path) -> None:
    """100 枚でも PDF 結合できること（性能境界）"""
    pngs = [_make_rgb_png(tmp_path / f"p_{i:03d}.png", size=(50, 50)) for i in range(100)]
    out = tmp_path / "many.pdf"
    build_pdf(pngs, out)
    assert len(PdfReader(str(out)).pages) == 100


def test_build_pdf_handles_thousand_pngs(tmp_path: Path) -> None:
    """リフロー型書籍で論理ページが膨らむケースの想定。

    現実装の `img2pdf.convert(...)` がメモリに全 PDF を載せると 1000 ページで
    数 GB に達する。ストリーム出力化することでメモリ消費を一定に保つ。
    """
    pngs = [_make_rgb_png(tmp_path / f"p_{i:04d}.png", size=(50, 50)) for i in range(1000)]
    out = tmp_path / "huge.pdf"
    build_pdf(pngs, out)
    assert len(PdfReader(str(out)).pages) == 1000


def test_build_pdf_streams_to_disk_without_loading_full_bytes_into_memory(
    tmp_path: Path,
) -> None:
    """ファイルが先に開かれて、stream で書き込まれること。

    実装上、`out_path.write_bytes(...)` で全データをメモリ経由する形ではなく、
    open(out_path, 'wb') の stream に img2pdf を直接書き出す形であるべき。

    検証は「途中で SIGINT 等で中断したとき、書きかけのファイルが一部だけ存在する」
    といった挙動の代わりに、`outputstream=` を使う実装かどうかをモックで判定する。
    """
    from unittest.mock import patch

    import img2pdf

    pngs = [_make_rgb_png(tmp_path / "x.png")]
    captured_kwargs: dict[str, Any] = {}

    real_convert = img2pdf.convert

    def spy(*args: Any, **kwargs: Any) -> Any:
        captured_kwargs.update(kwargs)
        return real_convert(*args, **kwargs)

    with patch("kindle_cap.pdf.img2pdf.convert", side_effect=spy):
        build_pdf(pngs, tmp_path / "out.pdf")

    assert "outputstream" in captured_kwargs, (
        "build_pdf は img2pdf.convert に outputstream を渡してストリーム出力する"
    )


def test_build_pdf_handles_different_sizes(tmp_path: Path) -> None:
    """異なる画素サイズの PNG が混在しても結合できる"""
    p1 = _make_rgb_png(tmp_path / "small.png", size=(100, 100))
    p2 = _make_rgb_png(tmp_path / "large.png", size=(500, 700))
    p3 = _make_rgb_png(tmp_path / "wide.png", size=(800, 200))
    out = tmp_path / "mixed.pdf"
    build_pdf([p1, p2, p3], out)
    reader = PdfReader(str(out))
    assert len(reader.pages) == 3


def test_build_pdf_overwrites_existing_pdf(sample_pngs: list[Path], tmp_path: Path) -> None:
    """既存 PDF があっても上書きされる"""
    out = tmp_path / "out.pdf"
    out.write_bytes(b"GARBAGE")
    build_pdf(sample_pngs, out)
    assert out.read_bytes()[:5] == b"%PDF-"
    assert len(PdfReader(str(out)).pages) == 3


def test_build_pdf_handles_japanese_filename(sample_pngs: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "テスト書籍.pdf"
    build_pdf(sample_pngs, out)
    assert out.exists()


def test_build_pdf_handles_path_with_spaces(sample_pngs: list[Path], tmp_path: Path) -> None:
    out_dir = tmp_path / "name with space"
    out_dir.mkdir()
    out = out_dir / "out.pdf"
    build_pdf(sample_pngs, out)
    assert out.exists()


def test_build_pdf_preserves_page_order(tmp_path: Path) -> None:
    """与えた PNG リストの順序で PDF が並ぶ"""
    pngs = [
        _make_rgb_png(tmp_path / "first.png", color="red"),
        _make_rgb_png(tmp_path / "second.png", color="green"),
        _make_rgb_png(tmp_path / "third.png", color="blue"),
    ]
    out = tmp_path / "ordered.pdf"
    build_pdf(pngs, out)
    reader = PdfReader(str(out))
    assert len(reader.pages) == 3
    # 順序の本格検証は PDF 内画像抽出が必要 — ここではページ数のみで妥協


# ---------------------------------------------------------------------------
# ディスク容量不足 (ENOSPC) ハンドリング
# ---------------------------------------------------------------------------


def test_pdf_build_error_is_exception_subclass() -> None:
    assert issubclass(PdfBuildError, Exception)


def test_build_pdf_raises_pdf_build_error_on_enospc(tmp_path: Path) -> None:
    """img2pdf が ENOSPC で OSError を投げたら PdfBuildError に変換される."""
    p = _make_rgb_png(tmp_path / "page_001.png")
    out = tmp_path / "out.pdf"

    enospc = OSError(errno.ENOSPC, "No space left on device")
    with (
        patch("kindle_cap.pdf.img2pdf.convert", side_effect=enospc),
        pytest.raises(PdfBuildError),
    ):
        build_pdf([p], out)


def test_build_pdf_removes_partial_pdf_on_enospc(tmp_path: Path) -> None:
    """ENOSPC 時、書きかけの PDF ファイルは残さない."""
    p = _make_rgb_png(tmp_path / "page_001.png")
    out = tmp_path / "out.pdf"

    enospc = OSError(errno.ENOSPC, "No space left on device")
    with (
        patch("kindle_cap.pdf.img2pdf.convert", side_effect=enospc),
        pytest.raises(PdfBuildError),
    ):
        build_pdf([p], out)

    assert not out.exists(), "部分書き込みされた PDF は削除されているべき"


def test_build_pdf_keeps_png_files_on_enospc(tmp_path: Path) -> None:
    """ENOSPC 時、入力 PNG は削除しない (再生成のため)."""
    p = _make_rgb_png(tmp_path / "page_001.png")
    out = tmp_path / "out.pdf"

    enospc = OSError(errno.ENOSPC, "No space left on device")
    with (
        patch("kindle_cap.pdf.img2pdf.convert", side_effect=enospc),
        pytest.raises(PdfBuildError),
    ):
        build_pdf([p], out)

    assert p.exists(), "入力 PNG は ENOSPC 時も保持される"


def test_build_pdf_error_message_includes_png_directory(tmp_path: Path) -> None:
    """エラーメッセージに PNG が残っている場所を含めて、ユーザーが再生成手順を分かる."""
    p = _make_rgb_png(tmp_path / "page_001.png")
    out = tmp_path / "out.pdf"

    enospc = OSError(errno.ENOSPC, "No space left on device")
    with (
        patch("kindle_cap.pdf.img2pdf.convert", side_effect=enospc),
        pytest.raises(PdfBuildError) as exc_info,
    ):
        build_pdf([p], out)

    assert str(tmp_path) in str(exc_info.value)


def test_build_pdf_reraises_non_enospc_oserror(tmp_path: Path) -> None:
    """ENOSPC 以外の OSError は PdfBuildError に変換せず原例外を raise."""
    p = _make_rgb_png(tmp_path / "page_001.png")
    out = tmp_path / "out.pdf"

    other = OSError(errno.EACCES, "Permission denied")
    with (
        patch("kindle_cap.pdf.img2pdf.convert", side_effect=other),
        pytest.raises(OSError) as exc_info,
    ):
        build_pdf([p], out)

    assert not isinstance(exc_info.value, PdfBuildError)
    assert exc_info.value.errno == errno.EACCES


def test_build_pdf_removes_partial_pdf_on_other_oserror(tmp_path: Path) -> None:
    """ENOSPC 以外の OSError でも部分書き込み PDF は削除される."""
    p = _make_rgb_png(tmp_path / "page_001.png")
    out = tmp_path / "out.pdf"

    other = OSError(errno.EIO, "I/O error")
    with patch("kindle_cap.pdf.img2pdf.convert", side_effect=other), pytest.raises(OSError):
        build_pdf([p], out)

    assert not out.exists(), "原例外 OSError でも部分 PDF は削除する"


# ---------------------------------------------------------------------------
# JPEG quality option (PDF サイズ縮小)
# ---------------------------------------------------------------------------


def _make_noisy_png(path: Path, size: tuple[int, int] = (400, 400)) -> Path:
    """JPEG 圧縮効果が現れるように、ノイズを含む PNG を生成する.

    単色 PNG だと JPEG / PNG どちらでも極小サイズに圧縮されるため、
    `--pdf-jpeg-quality` の効果検証には判定不能。`Image.effect_noise` で
    高エントロピーのグレー画像を作り、PNG (lossless) と JPEG (lossy)
    のサイズ差を実測可能にする。
    """
    Image.effect_noise(size, sigma=64).convert("RGB").save(path, format="PNG")
    return path


def test_build_pdf_jpeg_quality_none_keeps_existing_path_input(tmp_path: Path) -> None:
    """jpeg_quality=None (デフォルト) では img2pdf にパス文字列リストを渡す (現状動作)."""
    pngs = [_make_rgb_png(tmp_path / "p.png")]
    captured_args: dict[str, Any] = {}

    real_convert = __import__("img2pdf").convert

    def spy(*args: Any, **kwargs: Any) -> Any:
        captured_args["positional"] = args
        return real_convert(*args, **kwargs)

    with patch("kindle_cap.pdf.img2pdf.convert", side_effect=spy):
        build_pdf(pngs, tmp_path / "out.pdf")

    first = captured_args["positional"][0]
    assert isinstance(first, list)
    assert all(isinstance(x, str) for x in first), (
        "jpeg_quality 未指定時はパス文字列のまま渡し、現状の lossless PNG embed を維持する"
    )


def test_build_pdf_jpeg_quality_passes_bytes_to_img2pdf(tmp_path: Path) -> None:
    """jpeg_quality 指定時は Pillow で JPEG bytes に変換した結果を img2pdf に渡す."""
    pngs = [_make_rgb_png(tmp_path / "p.png")]
    captured_args: dict[str, Any] = {}

    real_convert = __import__("img2pdf").convert

    def spy(*args: Any, **kwargs: Any) -> Any:
        captured_args["positional"] = args
        return real_convert(*args, **kwargs)

    with patch("kindle_cap.pdf.img2pdf.convert", side_effect=spy):
        build_pdf(pngs, tmp_path / "out.pdf", jpeg_quality=80)

    first = captured_args["positional"][0]
    assert isinstance(first, list)
    assert all(isinstance(x, bytes) for x in first)
    assert first[0].startswith(b"\xff\xd8\xff"), "JPEG SOI marker (FFD8FF) で始まる bytes である"


def test_build_pdf_jpeg_quality_creates_smaller_pdf(tmp_path: Path) -> None:
    """ノイズ画像で JPEG 80 と lossless PNG の PDF サイズを比較し、JPEG 版が小さいこと."""
    pngs = [_make_noisy_png(tmp_path / f"p_{i}.png") for i in range(3)]
    out_lossless = tmp_path / "lossless.pdf"
    out_jpeg = tmp_path / "jpeg.pdf"

    build_pdf(pngs, out_lossless)
    build_pdf(pngs, out_jpeg, jpeg_quality=50)

    lossless_size = out_lossless.stat().st_size
    jpeg_size = out_jpeg.stat().st_size
    assert jpeg_size < lossless_size, (
        f"JPEG quality=50 (size={jpeg_size}) は lossless (size={lossless_size}) より小さくなるべき"
    )


def test_build_pdf_jpeg_quality_produces_valid_pdf(tmp_path: Path) -> None:
    """jpeg_quality 指定時も pypdf でページ数が読める正しい PDF を生成する."""
    pngs = [_make_rgb_png(tmp_path / f"p_{i}.png") for i in range(3)]
    out = tmp_path / "out.pdf"
    build_pdf(pngs, out, jpeg_quality=80)
    assert len(PdfReader(str(out)).pages) == 3


def test_build_pdf_jpeg_quality_handles_rgba_png(tmp_path: Path) -> None:
    """RGBA PNG (透過あり) も JPEG 変換できる (RGB に flatten される)."""
    p = tmp_path / "rgba.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 128)).save(p)
    out = tmp_path / "rgba.pdf"
    build_pdf([p], out, jpeg_quality=80)
    assert len(PdfReader(str(out)).pages) == 1


def test_build_pdf_rejects_jpeg_quality_too_low(tmp_path: Path) -> None:
    p = _make_rgb_png(tmp_path / "p.png")
    with pytest.raises(ValueError, match="jpeg_quality"):
        build_pdf([p], tmp_path / "out.pdf", jpeg_quality=0)


def test_build_pdf_rejects_jpeg_quality_too_high(tmp_path: Path) -> None:
    p = _make_rgb_png(tmp_path / "p.png")
    with pytest.raises(ValueError, match="jpeg_quality"):
        build_pdf([p], tmp_path / "out.pdf", jpeg_quality=101)


def test_build_pdf_accepts_jpeg_quality_boundaries(tmp_path: Path) -> None:
    """境界値 1 / 100 は受理する."""
    p = _make_rgb_png(tmp_path / "p.png")
    build_pdf([p], tmp_path / "q1.pdf", jpeg_quality=1)
    build_pdf([p], tmp_path / "q100.pdf", jpeg_quality=100)
    assert (tmp_path / "q1.pdf").exists()
    assert (tmp_path / "q100.pdf").exists()


# ---------------------------------------------------------------------------
# Progress (tqdm) option for JPEG conversion loop (issue #53)
# ---------------------------------------------------------------------------


def test_build_pdf_progress_default_does_not_use_tqdm(tmp_path: Path) -> None:
    """progress=False (デフォルト) では tqdm でラップされない."""
    pngs = [_make_rgb_png(tmp_path / f"p_{i}.png") for i in range(3)]
    with patch("kindle_cap.pdf.tqdm") as mock_tqdm:
        build_pdf(pngs, tmp_path / "out.pdf", jpeg_quality=80)
    mock_tqdm.assert_not_called()


def test_build_pdf_progress_true_wraps_jpeg_loop_with_tqdm(tmp_path: Path) -> None:
    """progress=True + jpeg_quality 指定 + 複数ページなら tqdm が呼ばれる."""
    pngs = [_make_rgb_png(tmp_path / f"p_{i}.png") for i in range(3)]
    with patch("kindle_cap.pdf.tqdm", side_effect=lambda it, **kw: it) as mock_tqdm:
        build_pdf(pngs, tmp_path / "out.pdf", jpeg_quality=80, progress=True)
    mock_tqdm.assert_called_once()
    # tqdm に渡される最初の引数は png_paths リスト
    args, _ = mock_tqdm.call_args
    assert args[0] == pngs


def test_build_pdf_progress_true_without_jpeg_quality_does_not_use_tqdm(
    tmp_path: Path,
) -> None:
    """jpeg_quality=None のときは JPEG ループがないため progress=True でも tqdm 不要."""
    pngs = [_make_rgb_png(tmp_path / f"p_{i}.png") for i in range(3)]
    with patch("kindle_cap.pdf.tqdm") as mock_tqdm:
        build_pdf(pngs, tmp_path / "out.pdf", progress=True)
    mock_tqdm.assert_not_called()


def test_build_pdf_progress_true_with_single_png_does_not_use_tqdm(
    tmp_path: Path,
) -> None:
    """1 ページのときは進捗バーが意味を持たないので tqdm を呼ばない."""
    p = _make_rgb_png(tmp_path / "only.png")
    with patch("kindle_cap.pdf.tqdm") as mock_tqdm:
        build_pdf([p], tmp_path / "out.pdf", jpeg_quality=80, progress=True)
    mock_tqdm.assert_not_called()


def test_build_pdf_progress_disables_tqdm_when_stderr_not_tty(
    tmp_path: Path,
) -> None:
    """非 tty (CI 等) では tqdm を呼ぶが disable=True を渡す."""
    pngs = [_make_rgb_png(tmp_path / f"p_{i}.png") for i in range(3)]
    with (
        patch("kindle_cap.pdf.sys.stderr.isatty", return_value=False),
        patch("kindle_cap.pdf.tqdm", side_effect=lambda it, **kw: it) as mock_tqdm,
    ):
        build_pdf(pngs, tmp_path / "out.pdf", jpeg_quality=80, progress=True)
    mock_tqdm.assert_called_once()
    _, kwargs = mock_tqdm.call_args
    assert kwargs.get("disable") is True
