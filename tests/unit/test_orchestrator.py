from pathlib import Path
from unittest.mock import patch

from kindle_cap.config import CaptureConfig, Direction, Geometry
from kindle_cap.orchestrator import _capture_book, _image_hash, run

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


# ---------------------------------------------------------------------------
# _capture_book: start_index / seed_hashes 拡張
# ---------------------------------------------------------------------------


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
def test_capture_book_with_start_index_skips_purge_and_resumes(
    mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path: Path,
) -> None:
    """start_index=4 のとき page_001..003 は採用されたまま、page_004 から撮影。
    最初のループ反復で先に send_next_page を呼ぶ。"""
    mock_geom.return_value = _GEOM
    out_dir = tmp_path / "bk"
    out_dir.mkdir()
    for i in range(1, 4):
        (out_dir / f"page_{i:03d}.png").write_bytes(b"existing")
    mock_cap.side_effect = lambda g, p: p.write_bytes(b"new")
    _capture_book(_config(tmp_path, pages=5), auto_stop=False, start_index=4)
    # 撮影は page_004, page_005 の 2 回
    assert mock_cap.call_count == 2
    # send_next_page: page_004 撮る前 + page_004 → page_005 移動 = 2 回
    assert mock_send.call_count == 2
    # PDF には 5 枚渡される（試写 3 + 新規 2）
    assert mock_pdf.call_args[0][0].__len__() == 5


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
def test_capture_book_with_start_index_one_purges_old_pages(
    mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path: Path,
) -> None:
    """通常の start_index=1 では既存 page_*.png を purge する（既存挙動）。"""
    mock_geom.return_value = _GEOM
    out_dir = tmp_path / "bk"
    out_dir.mkdir()
    stale = out_dir / "page_001.png"
    stale.write_bytes(b"stale")
    mock_cap.side_effect = lambda g, p: p.write_bytes(b"new")
    _capture_book(_config(tmp_path, pages=2), auto_stop=False, start_index=1)
    # purge されて mock_cap で書き直されている
    assert stale.read_bytes() == b"new"


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
def test_capture_book_with_seed_hashes_stops_immediately_when_first_page_matches(
    mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path: Path,
) -> None:
    """seed_hashes の最後と本番初回ページのハッシュが一致すれば auto_stop が即停止。"""
    mock_geom.return_value = _GEOM
    out_dir = tmp_path / "bk"
    out_dir.mkdir()
    for i in range(1, 4):
        (out_dir / f"page_{i:03d}.png").write_bytes(f"page-{i}".encode())
    last_seed_hash = _image_hash(out_dir / "page_003.png")
    # page_004 を撮るとき page_003 と同一バイトを書く → 即停止
    mock_cap.side_effect = lambda g, p: p.write_bytes(b"page-3")
    _capture_book(
        _config(tmp_path, pages=10),
        auto_stop=True,
        start_index=4,
        seed_hashes=[
            _image_hash(out_dir / "page_001.png"),
            _image_hash(out_dir / "page_002.png"),
            last_seed_hash,
        ],
    )
    # page_004.png は重複検出で削除される
    assert not (out_dir / "page_004.png").exists()
    # PDF には試写 3 枚のみ
    assert mock_pdf.call_args[0][0].__len__() == 3


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
def test_capture_book_passes_existing_pages_to_pdf_when_start_index_gt_one(
    mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path: Path,
) -> None:
    """page_001..start_index-1.png が PDF 入力に含まれる。"""
    mock_geom.return_value = _GEOM
    out_dir = tmp_path / "bk"
    out_dir.mkdir()
    for i in range(1, 4):
        (out_dir / f"page_{i:03d}.png").write_bytes(f"existing-{i}".encode())
    mock_cap.side_effect = lambda g, p: p.write_bytes(b"new")
    _capture_book(_config(tmp_path, pages=5), auto_stop=False, start_index=4)
    pdf_inputs = mock_pdf.call_args[0][0]
    assert [p.name for p in pdf_inputs] == [
        "page_001.png", "page_002.png", "page_003.png",
        "page_004.png", "page_005.png",
    ]


@patch("kindle_cap.orchestrator.build_pdf")
@patch("kindle_cap.orchestrator.send_next_page")
@patch("kindle_cap.orchestrator.capture_rect")
@patch("kindle_cap.orchestrator.get_window_geometry")
@patch("kindle_cap.orchestrator.activate_kindle")
def test_capture_book_default_start_index_unchanged_behavior(
    mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path: Path,
) -> None:
    """start_index 引数を渡さない既存呼び出しは挙動不変（page_001 から N 枚撮る）。"""
    mock_geom.return_value = _GEOM
    mock_cap.side_effect = lambda g, p: p.write_bytes(f"u-{p.name}".encode())
    _capture_book(_config(tmp_path, pages=3), auto_stop=False)
    assert mock_cap.call_count == 3
    assert mock_send.call_count == 2  # 最終ページ後は送らない
    assert mock_pdf.call_args[0][0].__len__() == 3
