from pathlib import Path
from unittest.mock import patch

from kindle_cap.config import CaptureConfig, Direction, Geometry
from kindle_cap.orchestrator import _image_hash, run

_GEOM = Geometry(x=0, y=0, width=100, height=100)


def _config(tmp_path: Path, **overrides) -> CaptureConfig:
    base = dict(
        name="bk",
        pages=3,
        direction=Direction.RTL,
        wait=0.0,
        out=tmp_path,
        keep_png=True,
    )
    base.update(overrides)
    return CaptureConfig(**base)


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_three_pages_calls_each_step_correctly(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    mock_geom.return_value = _GEOM
    run(_config(tmp_path, pages=3))
    assert mock_pre.call_count == 1
    assert mock_act.call_count == 3
    assert mock_geom.call_count == 3
    assert mock_cap.call_count == 3
    assert mock_send.call_count == 2  # 最終ページ後は送らない
    mock_pdf.assert_called_once()


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_dry_run_takes_one_shot_and_skips_pdf(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    mock_geom.return_value = _GEOM
    run(_config(tmp_path), dry_run=True)
    assert mock_cap.call_count == 1
    assert mock_send.call_count == 0
    mock_pdf.assert_not_called()


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_dry_run_writes_to_dry_run_png(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    mock_geom.return_value = _GEOM
    run(_config(tmp_path), dry_run=True)
    out_path = mock_cap.call_args[0][1]
    assert out_path.name == "dry_run.png"


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_keyboard_interrupt_keeps_partial_and_skips_pdf(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    mock_geom.return_value = _GEOM
    mock_cap.side_effect = [None, KeyboardInterrupt(), None]
    run(_config(tmp_path, pages=5))
    mock_pdf.assert_not_called()


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_deletes_existing_pngs_before_capture(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    mock_geom.return_value = _GEOM
    out_dir = tmp_path / "bk"
    out_dir.mkdir()
    stale = out_dir / "page_999.png"
    stale.write_bytes(b"old")
    run(_config(tmp_path, pages=2, name="bk"))
    assert not stale.exists()


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_no_keep_png_removes_pngs_after_pdf(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    mock_geom.return_value = _GEOM

    def touch(geom, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    mock_cap.side_effect = touch
    run(_config(tmp_path, pages=2, keep_png=False))
    assert not (tmp_path / "bk" / "page_001.png").exists()
    assert not (tmp_path / "bk" / "page_002.png").exists()


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_writes_pdf_to_out_root(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    mock_geom.return_value = _GEOM
    run(_config(tmp_path, name="hello", pages=2))
    pdf_path = mock_pdf.call_args[0][1]
    assert pdf_path == tmp_path / "hello.pdf"


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_prints_progress_for_each_page(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
    capsys,
):
    """長尺キャプチャの UX として、各ページごとに進捗を出すこと"""
    mock_geom.return_value = _GEOM
    run(_config(tmp_path, pages=3))
    out = capsys.readouterr().out
    assert "1/3" in out
    assert "2/3" in out
    assert "3/3" in out


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_progress_reflects_actual_page_count(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
    capsys,
):
    """N ページ指定なら 'N/N' まで含まれること（最終ページの進捗が抜けないこと）"""
    mock_geom.return_value = _GEOM
    run(_config(tmp_path, pages=10))
    out = capsys.readouterr().out
    assert "10/10" in out


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_dry_run_does_not_print_progress_count(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
    capsys,
):
    """dry-run はループしないので 1/N 形式の進捗は出ない"""
    mock_geom.return_value = _GEOM
    run(_config(tmp_path, pages=1), dry_run=True)
    out = capsys.readouterr().out
    assert "1/1" not in out


# ---------------------------------------------------------------------------
# auto-stop: 連続する重複ページで終端検出
# ---------------------------------------------------------------------------


def _capture_factory_with_termination(unique_pages: int):
    """unique_pages 枚目までは別内容、それ以降は最後の内容を繰り返す側"""
    counter = {"n": 0}

    def _capture(geom, path):
        counter["n"] += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        if counter["n"] <= unique_pages:
            path.write_bytes(f"page-{counter['n']}".encode())
        else:
            path.write_bytes(f"page-{unique_pages}".encode())

    return _capture


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_auto_stop_halts_on_duplicate_consecutive_pages(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    """3 ユニークページの後に同一ページ繰り返し → auto-stop で 3 ページのみ取る"""
    mock_geom.return_value = _GEOM
    mock_cap.side_effect = _capture_factory_with_termination(unique_pages=3)
    run(_config(tmp_path, pages=20), auto_stop=True)
    pngs_arg = mock_pdf.call_args[0][0]
    assert len(pngs_arg) == 3


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_auto_stop_off_keeps_full_pages(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    """auto_stop=False（デフォルト）なら、重複ページがあっても指定 N ページ全部撮る"""
    mock_geom.return_value = _GEOM
    mock_cap.side_effect = _capture_factory_with_termination(unique_pages=3)
    run(_config(tmp_path, pages=10), auto_stop=False)
    pngs_arg = mock_pdf.call_args[0][0]
    assert len(pngs_arg) == 10


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_auto_stop_removes_duplicate_png_from_disk(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    """終端検出時に書いた重複 PNG ファイルは削除されること"""
    mock_geom.return_value = _GEOM
    mock_cap.side_effect = _capture_factory_with_termination(unique_pages=2)
    run(_config(tmp_path, pages=10), auto_stop=True)
    out_dir = tmp_path / "bk"
    pages = sorted(out_dir.glob("page_*.png"))
    assert len(pages) == 2  # ユニーク 2 枚だけ残る


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
@patch("kindle_cap.orchestrator.preflight")
def test_run_auto_stop_with_all_unique_pages_takes_full_count(
    mock_pre,
    mock_act,
    mock_geom,
    mock_cap,
    mock_send,
    mock_pdf,
    tmp_path,
):
    """全ページがユニークなら、auto_stop でも N 枚撮る"""
    mock_geom.return_value = _GEOM
    counter = {"n": 0}

    def _all_unique(geom, path):
        counter["n"] += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"unique-{counter['n']}".encode())

    mock_cap.side_effect = _all_unique
    run(_config(tmp_path, pages=5), auto_stop=True)
    assert mock_pdf.call_args[0][0].__len__() == 5


def test_image_hash_returns_md5_hex(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello")
    assert _image_hash(p) == "5d41402abc4b2a76b9719d911017c592"


def test_image_hash_changes_on_byte_change(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello")
    h1 = _image_hash(p)
    p.write_bytes(b"hello!")
    assert h1 != _image_hash(p)
