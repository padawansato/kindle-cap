"""Orchestrate the capture loop, dry-run, and PDF assembly."""
from pathlib import Path
from time import sleep

from .capture import capture_rect
from .config import CaptureConfig
from .keys import send_next_page
from .pdf import build_pdf
from .preflight import preflight
from .window import activate_kindle, get_window_geometry


def run(config: CaptureConfig, dry_run: bool = False) -> None:
    preflight()
    config.out.mkdir(parents=True, exist_ok=True)

    if dry_run:
        _run_dry(config)
        return

    out_dir = config.out / config.name
    out_dir.mkdir(parents=True, exist_ok=True)
    _purge_old_pages(out_dir)

    captured: list[Path] = []
    try:
        for i in range(1, config.pages + 1):
            activate_kindle()
            geom = get_window_geometry()
            png_path = out_dir / f"page_{i:03d}.png"
            capture_rect(geom, png_path)
            captured.append(png_path)
            if i < config.pages:
                send_next_page(config.direction)
                sleep(config.wait)
    except KeyboardInterrupt:
        print(
            f"\n中断しました。{len(captured)}/{config.pages} ページまで撮影済み。"
            " PNG は保持し、PDF は作成しません。"
        )
        return

    pdf_path = config.out / f"{config.name}.pdf"
    build_pdf(captured, pdf_path)

    if not config.keep_png:
        for p in captured:
            p.unlink(missing_ok=True)
        try:
            out_dir.rmdir()
        except OSError:
            pass

    print(f"完了: {pdf_path}")


def _run_dry(config: CaptureConfig) -> None:
    activate_kindle()
    geom = get_window_geometry()
    dry_path = config.out / "dry_run.png"
    capture_rect(geom, dry_path)
    print(
        f"window geometry: x={geom.x} y={geom.y} "
        f"w={geom.width} h={geom.height}"
    )
    print(f"saved: {dry_path}")


def _purge_old_pages(out_dir: Path) -> None:
    for p in out_dir.glob("page_*.png"):
        p.unlink()
