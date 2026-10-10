"""Orchestrate the capture loop, dry-run, and PDF assembly."""

import contextlib
import dataclasses
import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from time import sleep

from .background import capture_kindle_window, post_next_page
from .capture import capture_rect, crop_top
from .config import CaptureConfig, Geometry
from .keys import send_next_page
from .pdf import build_pdf
from .preflight import detect_direction, preflight
from .window import activate_kindle, get_window_geometry

logger = logging.getLogger(__name__)


def _window_geometry(config: CaptureConfig) -> Geometry:
    """Kindle ウィンドウ frame を取り、config.crop_top ぶん上端を削って返す (issue #69)."""
    return crop_top(get_window_geometry(), config.crop_top)


_OFFSCREEN_POLL_SEC = 2.0


def _capture_background(config: CaptureConfig, png_path: Path) -> None:
    """窓 ID 指定で撮る。窓が offscreen (hide / minimize / 別 Space) の間は失敗にせず待つ."""
    warned = False
    while not capture_kindle_window(png_path, crop_top=config.crop_top):
        if not warned:
            logger.warning(
                "Kindle の窓が画面上にありません (隠した / 最小化した / 別のデスクトップ)。"
                "表示されるまで待ちます"
            )
            warned = True
        sleep(_OFFSCREEN_POLL_SEC)
    if warned:
        logger.info("Kindle の窓が戻ったので再開します")


def _capture_page(
    config: CaptureConfig, png_path: Path, before_capture: Callable[[], None] | None
) -> None:
    if config.background:
        if before_capture is not None:
            before_capture()
        _capture_background(config, png_path)
        return
    activate_kindle()
    if before_capture is not None:
        before_capture()
    capture_rect(_window_geometry(config), png_path)


def _next_page(config: CaptureConfig) -> None:
    assert config.direction is not None
    if config.background:
        post_next_page(config.direction)
    else:
        send_next_page(config.direction)


def run(
    config: CaptureConfig,
    dry_run: bool = False,
    auto_stop: bool = False,
    auto_direction: bool = False,
    before_capture: Callable[[], None] | None = None,
) -> None:
    """`before_capture` は各ページの撮影直前 (activate 後) に呼ぶフック。
    kindle-cap-all がリーダーに被さるシート (サンプル末尾の「著者をフォロー」等) を
    閉じるのに使う。"""
    preflight()
    config.out.mkdir(parents=True, exist_ok=True)

    if dry_run:
        _run_dry(config)
        return

    if config.background:
        # 開始時に 1 回だけ前面に出す (hide されていれば解除される)。以後は奪わない。
        # activate 直後の再描画中に撮らないよう wait ぶん落ち着かせる
        activate_kindle()
        sleep(config.wait)

    if auto_direction:
        out_dir = config.out / config.name
        out_dir.mkdir(parents=True, exist_ok=True)
        _purge_old_pages(out_dir)

        resolved_direction, initial_pngs = detect_direction(
            out_dir=out_dir,
            geom_provider=lambda: _window_geometry(config),
            activator=(lambda: None) if config.background else activate_kindle,
            capturer=(
                (lambda _geom, path: _capture_background(config, path))
                if config.background
                else capture_rect
            ),
            sender=post_next_page if config.background else send_next_page,
            sleeper=sleep,
            wait=config.wait,
        )
        resolved_config = dataclasses.replace(config, direction=resolved_direction)

        seed_hashes = [_image_hash(p) for p in initial_pngs]
        _capture_book(
            resolved_config,
            auto_stop=auto_stop,
            start_index=len(initial_pngs) + 1,
            seed_hashes=seed_hashes,
            before_capture=before_capture,
        )
        return

    if config.direction is None:
        raise ValueError("direction を指定してください（または auto_direction=True を使用）")
    _capture_book(config, auto_stop=auto_stop, before_capture=before_capture)


def _image_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _capture_book(
    config: CaptureConfig,
    *,
    auto_stop: bool,
    start_index: int = 1,
    seed_hashes: list[str] | None = None,
    before_capture: Callable[[], None] | None = None,
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
    end_detected = False
    try:
        for i in range(start_index, config.pages + 1):
            # 試写流用時の最初の反復は、試写ループ末尾で矢印を送っていないため
            # 先にページを進めてから撮影する
            if i == start_index and start_index > 1:
                _next_page(config)
                sleep(config.wait)

            logger.info("[%d/%d] capturing page", i, config.pages)
            png_path = out_dir / f"page_{i:03d}.png"
            try:
                _capture_page(config, png_path, before_capture)
            except Exception:
                logger.exception(
                    "page %d/%d capture failed (captured so far: %d, out_dir=%s)",
                    i,
                    config.pages,
                    len(captured),
                    out_dir,
                )
                raise

            if auto_stop:
                current_hash = _image_hash(png_path)
                if current_hash == last_hash:
                    png_path.unlink(missing_ok=True)
                    logger.info("終端を検出（前ページと同一）。%d ページで停止", len(captured))
                    end_detected = True
                    break
                last_hash = current_hash

            captured.append(png_path)
            if i < config.pages:
                _next_page(config)
                sleep(config.wait)
    except KeyboardInterrupt:
        logger.warning(
            "中断しました。%d/%d ページまで撮影済み。PNG は保持し、PDF は作成しません。",
            len(captured),
            config.pages,
        )
        return

    if not captured:
        logger.warning("撮影 0 ページ。%s の PDF はスキップ", config.name)
        return

    if auto_stop and not end_detected:
        # 終端で止まったのか上限で切れたのかを後から区別できるようにする
        logger.warning(
            "上限 %d ページに達したため停止。書籍末尾は未検出です（--max-pages を増やして再実行）",
            config.pages,
        )

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

    logger.info("完了: %s", pdf_path)


def _run_dry(config: CaptureConfig) -> None:
    dry_path = config.out / "dry_run.png"
    if config.background:
        _capture_background(config, dry_path)
        logger.info("saved: %s", dry_path)
        return
    activate_kindle()
    geom = _window_geometry(config)
    capture_rect(geom, dry_path)
    logger.info("window geometry: x=%d y=%d w=%d h=%d", geom.x, geom.y, geom.width, geom.height)
    logger.info("saved: %s", dry_path)


def _purge_old_pages(out_dir: Path) -> None:
    for p in out_dir.glob("page_*.png"):
        p.unlink()
