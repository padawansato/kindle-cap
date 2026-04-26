"""Orchestrate the capture loop, dry-run, and PDF assembly."""

import contextlib
import hashlib
from pathlib import Path
from time import sleep

from .capture import capture_rect
from .config import CaptureConfig
from .keys import send_next_page
from .pdf import build_pdf
from .preflight import preflight
from .window import activate_kindle, get_window_geometry


def run(
    config: CaptureConfig,
    dry_run: bool = False,
    auto_stop: bool = False,
) -> None:
    preflight()
    config.out.mkdir(parents=True, exist_ok=True)

    if dry_run:
        _run_dry(config)
        return

    _capture_book(config, auto_stop=auto_stop)


def _image_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _capture_book(config: CaptureConfig, *, auto_stop: bool) -> None:
    """preflight 抜きの単一書籍撮影。"""
    out_dir = config.out / config.name
    out_dir.mkdir(parents=True, exist_ok=True)
    _purge_old_pages(out_dir)

    captured: list[Path] = []
    last_hash: str | None = None
    try:
        for i in range(1, config.pages + 1):
            print(f"[{i}/{config.pages}] capturing page", flush=True)
            activate_kindle()
            geom = get_window_geometry()
            png_path = out_dir / f"page_{i:03d}.png"
            capture_rect(geom, png_path)

            if auto_stop:
                current_hash = _image_hash(png_path)
                if current_hash == last_hash:
                    png_path.unlink(missing_ok=True)
                    print(
                        f"終端を検出（前ページと同一）。{len(captured)} ページで停止",
                        flush=True,
                    )
                    break
                last_hash = current_hash

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

    if not captured:
        print(f"撮影 0 ページ。{config.name} の PDF はスキップ", flush=True)
        return

    pdf_path = config.out / f"{config.name}.pdf"
    build_pdf(captured, pdf_path)

    if not config.keep_png:
        for p in captured:
            p.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            out_dir.rmdir()

    print(f"完了: {pdf_path}")


def _run_dry(config: CaptureConfig) -> None:
    activate_kindle()
    geom = get_window_geometry()
    dry_path = config.out / "dry_run.png"
    capture_rect(geom, dry_path)
    print(f"window geometry: x={geom.x} y={geom.y} w={geom.width} h={geom.height}")
    print(f"saved: {dry_path}")


def _purge_old_pages(out_dir: Path) -> None:
    for p in out_dir.glob("page_*.png"):
        p.unlink()
