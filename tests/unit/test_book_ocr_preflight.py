"""book_ocr.preflight のテスト (issue #48)."""

from __future__ import annotations

from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

import pytest

from book_ocr.preflight import (
    PreflightError,
    check_disk_space,
    estimate_required_bytes,
)

_DiskUsage = namedtuple("_DiskUsage", ["total", "used", "free"])


def _png(path: Path, size_bytes: int = 1024) -> Path:
    path.write_bytes(b"\x00" * size_bytes)
    return path


# ---------------------------------------------------------------------------
# estimate_required_bytes
# ---------------------------------------------------------------------------


def test_estimate_empty_returns_zero() -> None:
    assert estimate_required_bytes([], chunk_size=None) == 0


def test_estimate_uses_15x_margin(tmp_path: Path) -> None:
    p = _png(tmp_path / "page_001.png", size_bytes=1000)
    assert estimate_required_bytes([p], chunk_size=None) == 1500


def test_estimate_chunk_size_only_counts_first_chunk(tmp_path: Path) -> None:
    """chunk_size 指定時は最初の chunk 分だけを集計対象に含める."""
    pngs = [_png(tmp_path / f"p_{i}.png", size_bytes=1000) for i in range(10)]
    assert estimate_required_bytes(pngs, chunk_size=3) == int(3 * 1000 * 1.5)


def test_estimate_chunk_size_none_counts_all(tmp_path: Path) -> None:
    pngs = [_png(tmp_path / f"p_{i}.png", size_bytes=1000) for i in range(5)]
    assert estimate_required_bytes(pngs, chunk_size=None) == int(5 * 1000 * 1.5)


def test_estimate_chunk_size_larger_than_pages_uses_all(tmp_path: Path) -> None:
    pngs = [_png(tmp_path / f"p_{i}.png", size_bytes=1000) for i in range(3)]
    # chunk_size=10 だが、pngs[:10] は 3 要素しかない
    assert estimate_required_bytes(pngs, chunk_size=10) == int(3 * 1000 * 1.5)


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------


def test_check_disk_space_passes_when_free_is_sufficient(tmp_path: Path) -> None:
    pngs = [_png(tmp_path / "p_001.png", size_bytes=1000)]
    fake = lambda _: _DiskUsage(total=10_000_000, used=0, free=10_000_000)  # noqa: E731
    # required ≒ 1500 bytes、free = 10 MB なので問題なし
    check_disk_space(
        pngs=pngs,
        out_dir=tmp_path,
        chunk_size=None,
        tempdir=tmp_path,
        disk_usage_fn=fake,
    )


def test_check_disk_space_raises_when_free_is_insufficient(tmp_path: Path) -> None:
    pngs = [_png(tmp_path / "p_001.png", size_bytes=10 * 1024 * 1024)]
    # 必要 ~15 MB、free 5 MB → 不足
    fake = lambda _: _DiskUsage(total=100_000_000, used=0, free=5 * 1024 * 1024)  # noqa: E731
    with pytest.raises(PreflightError, match="ディスク容量不足"):
        check_disk_space(
            pngs=pngs,
            out_dir=tmp_path,
            chunk_size=None,
            tempdir=tmp_path,
            disk_usage_fn=fake,
        )


def test_check_disk_space_message_includes_required_and_free(tmp_path: Path) -> None:
    pngs = [_png(tmp_path / "p_001.png", size_bytes=10 * 1024 * 1024)]
    fake = lambda _: _DiskUsage(total=100_000_000, used=0, free=5 * 1024 * 1024)  # noqa: E731
    with pytest.raises(PreflightError) as exc_info:
        check_disk_space(
            pngs=pngs,
            out_dir=tmp_path,
            chunk_size=None,
            tempdir=tmp_path,
            disk_usage_fn=fake,
        )
    msg = str(exc_info.value)
    assert "MB" in msg
    assert "1 ページ" in msg
    assert "--ignore-disk-check" in msg


def test_check_disk_space_empty_pngs_is_noop(tmp_path: Path) -> None:
    called: list[Path] = []

    def fake(p: Path) -> _DiskUsage:
        called.append(p)
        return _DiskUsage(total=0, used=0, free=0)

    check_disk_space(
        pngs=[],
        out_dir=tmp_path,
        chunk_size=None,
        tempdir=tmp_path,
        disk_usage_fn=fake,
    )
    # required=0 のため disk_usage_fn は呼ばれない
    assert called == []


def test_check_disk_space_chunk_size_relaxes_requirement(tmp_path: Path) -> None:
    """chunk_size 指定時は 1 chunk 分しか見ないので、足りる残量が小さくて済む."""
    pngs = [_png(tmp_path / f"p_{i:03d}.png", size_bytes=10 * 1024 * 1024) for i in range(10)]
    # 必要 (chunk_size=1) ≒ 15 MB、free 20 MB → 通る
    fake = lambda _: _DiskUsage(total=100_000_000, used=0, free=20 * 1024 * 1024)  # noqa: E731
    check_disk_space(
        pngs=pngs,
        out_dir=tmp_path,
        chunk_size=1,
        tempdir=tmp_path,
        disk_usage_fn=fake,
    )


def test_check_disk_space_chunk_size_none_fails_when_total_too_large(tmp_path: Path) -> None:
    """chunk_size=None だと全 PNG 分要求するため、同じ free でも足りないことがある."""
    pngs = [_png(tmp_path / f"p_{i:03d}.png", size_bytes=10 * 1024 * 1024) for i in range(10)]
    # 必要 ≒ 150 MB、free 20 MB → 不足
    fake = lambda _: _DiskUsage(total=200_000_000, used=0, free=20 * 1024 * 1024)  # noqa: E731
    with pytest.raises(PreflightError):
        check_disk_space(
            pngs=pngs,
            out_dir=tmp_path,
            chunk_size=None,
            tempdir=tmp_path,
            disk_usage_fn=fake,
        )


def test_check_disk_space_resolves_nonexistent_out_dir_to_parent(tmp_path: Path) -> None:
    """まだ作成されていない out_dir でも、祖先に遡って残量を確認できる."""
    pngs = [_png(tmp_path / "p_001.png", size_bytes=1000)]
    not_yet = tmp_path / "does" / "not" / "exist"
    seen: list[Path] = []

    def fake(p: Path) -> _DiskUsage:
        seen.append(p)
        return _DiskUsage(total=10_000_000, used=0, free=10_000_000)

    check_disk_space(
        pngs=pngs,
        out_dir=not_yet,
        chunk_size=None,
        tempdir=tmp_path,
        disk_usage_fn=fake,
    )
    # 既存祖先 (tmp_path 配下のどこか) が disk_usage に渡されている
    assert any(str(tmp_path) in str(s) for s in seen)


def test_check_disk_space_skips_same_device(tmp_path: Path) -> None:
    """out_dir と tempdir が同一マウントなら 2 回チェックしない."""
    pngs = [_png(tmp_path / "p_001.png", size_bytes=1000)]
    call_count = 0

    def fake(_: Path) -> _DiskUsage:
        nonlocal call_count
        call_count += 1
        return _DiskUsage(total=10_000_000, used=0, free=10_000_000)

    check_disk_space(
        pngs=pngs,
        out_dir=tmp_path,
        chunk_size=None,
        tempdir=tmp_path,
        disk_usage_fn=fake,
    )
    assert call_count == 1


def test_check_disk_space_uses_system_tempdir_when_tempdir_is_none(tmp_path: Path) -> None:
    """tempdir=None なら tempfile.gettempdir() を参照する."""
    pngs = [_png(tmp_path / "p_001.png", size_bytes=1000)]
    seen: list[Path] = []

    def fake(p: Path) -> _DiskUsage:
        seen.append(p)
        return _DiskUsage(total=10_000_000, used=0, free=10_000_000)

    check_disk_space(
        pngs=pngs,
        out_dir=tmp_path,
        chunk_size=None,
        tempdir=None,
        disk_usage_fn=fake,
    )
    # tmp_path と system tempdir のどちらかが呼ばれる (同一マウントの可能性もある)
    assert len(seen) >= 1


def test_check_disk_space_uses_real_disk_usage_by_default(tmp_path: Path) -> None:
    """`disk_usage_fn` を渡さない場合は shutil.disk_usage を使う."""
    pngs = [_png(tmp_path / "p_001.png", size_bytes=1)]
    # 実 disk_usage で通る (普段の開発機なら数 bytes は十分余る)
    check_disk_space(pngs=pngs, out_dir=tmp_path, chunk_size=None, tempdir=tmp_path)


# ---------------------------------------------------------------------------
# cli 統合: --ignore-disk-check / preflight 失敗の伝搬
# ---------------------------------------------------------------------------


def _make_book_dir(tmp_path: Path, n_pages: int = 2) -> Path:
    book = tmp_path / "my-book"
    book.mkdir()
    for i in range(1, n_pages + 1):
        (book / f"page_{i:03d}.png").write_bytes(b"\x00" * 1024)
    return book


def test_run_ocr_pipeline_calls_check_disk_space_by_default(tmp_path: Path) -> None:
    """run_ocr_pipeline は preflight を呼ぶ (ignore_disk_check=False がデフォルト)."""
    from book_ocr.cli import run_ocr_pipeline

    book = _make_book_dir(tmp_path, n_pages=2)

    with patch("book_ocr.cli.check_disk_space") as mock_check:
        # FakeEngine 注入 (yomitoku を呼ばない)
        from tests.unit.test_book_ocr_cli import FakeEngine

        run_ocr_pipeline(book_dir=book, engine=FakeEngine())

    mock_check.assert_called_once()


def test_run_ocr_pipeline_skips_check_when_ignore_flag_set(tmp_path: Path) -> None:
    from book_ocr.cli import run_ocr_pipeline

    book = _make_book_dir(tmp_path, n_pages=2)

    with patch("book_ocr.cli.check_disk_space") as mock_check:
        from tests.unit.test_book_ocr_cli import FakeEngine

        run_ocr_pipeline(book_dir=book, engine=FakeEngine(), ignore_disk_check=True)

    mock_check.assert_not_called()


def test_run_ocr_pipeline_propagates_preflight_error(tmp_path: Path) -> None:
    """check_disk_space が PreflightError を投げたら run_ocr_pipeline に伝搬する."""
    from book_ocr.cli import run_ocr_pipeline

    book = _make_book_dir(tmp_path, n_pages=2)

    with (
        patch(
            "book_ocr.cli.check_disk_space",
            side_effect=PreflightError("disk full"),
        ),
        pytest.raises(PreflightError, match="disk full"),
    ):
        from tests.unit.test_book_ocr_cli import FakeEngine

        run_ocr_pipeline(book_dir=book, engine=FakeEngine())
