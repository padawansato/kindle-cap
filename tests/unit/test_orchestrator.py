from pathlib import Path
from unittest.mock import patch

from kindle_cap.config import CaptureConfig, Direction, Geometry
from kindle_cap.orchestrator import run

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
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
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
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
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
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
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
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
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
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
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
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
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
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    mock_geom.return_value = _GEOM
    run(_config(tmp_path, name="hello", pages=2))
    pdf_path = mock_pdf.call_args[0][1]
    assert pdf_path == tmp_path / "hello.pdf"
