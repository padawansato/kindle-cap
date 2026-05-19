"""Orchestrate the capture loop, dry-run, and PDF assembly."""

import contextlib
import dataclasses
import hashlib
from pathlib import Path
from time import sleep

from .capture import capture_rect
from .config import CaptureConfig
from .keys import send_next_page
from .pdf import build_pdf
from .preflight import detect_direction, preflight
from .window import activate_kindle, get_window_geometry


def run(
    config: CaptureConfig,
    dry_run: bool = False,
    auto_stop: bool = False,
    auto_direction: bool = False,
) -> None:
    preflight()
    config.out.mkdir(parents=True, exist_ok=True)

    if dry_run:
        _run_dry(config)
        return

    if auto_direction:
        out_dir = config.out / config.name
        out_dir.mkdir(parents=True, exist_ok=True)
        _purge_old_pages(out_dir)

        resolved_direction, probe_pngs = detect_direction(
            out_dir=out_dir,
            geom_provider=get_window_geometry,
            activator=activate_kindle,
            capturer=capture_rect,
            sender=send_next_page,
            sleeper=sleep,
            wait=config.wait,
        )
        resolved_config = dataclasses.replace(config, direction=resolved_direction)

        if probe_pngs:
            seed_hashes = [_image_hash(p) for p in probe_pngs]
            _capture_book(
                resolved_config,
                auto_stop=auto_stop,
                start_index=len(probe_pngs) + 1,
                seed_hashes=seed_hashes,
            )
        else:
            _capture_book(resolved_config, auto_stop=auto_stop)
        return

    if config.direction is None:
        raise ValueError("direction を指定してください（または auto_direction=True を使用）")
    _capture_book(config, auto_stop=auto_stop)


def _image_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _capture_book(
    config: CaptureConfig,
    *,
    auto_stop: bool,
    start_index: int = 1,
    seed_hashes: list[str] | None = None,
) -> None:
    """preflight 抜きの単一書籍撮影。direction は確定済みで呼ばれる前提。

    start_index > 1 の場合は試写流用モード:
        - out_dir の page_001..start_index-1.png を既存ページとして captured に含める
        - _purge_old_pages は呼ばない（試写を保護）
        - 最初の反復は先に send_next_page を送る（試写ループ末尾は矢印未送信のため）
    seed_hashes: auto_stop の last_hash 初期値として使うハッシュ列（試写ハッシュなど）。
    """
    assert config.direction is not None, "_capture_book requires resolved direction"
    out_dir = config.out / config.name
    out_dir.mkdir(parents=True, exist_ok=True)
    if start_index == 1:
        _purge_old_pages(out_dir)

    captured: list[Path] = []
    if start_index > 1:
        for i in range(1, start_index):
            captured.append(out_dir / f"page_{i:03d}.png")

    last_hash: str | None = seed_hashes[-1] if seed_hashes else None
    try:
        for i in range(start_index, config.pages + 1):
            # 試写流用時の最初の反復は、試写ループ末尾で矢印を送っていないため
            # 先にページを進めてから撮影する
            if i == start_index and start_index > 1:
                send_next_page(config.direction)
                sleep(config.wait)

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
    build_pdf(
        captured,
        pdf_path,
        jpeg_quality=config.pdf_jpeg_quality,
        progress=config.progress,
    )

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
