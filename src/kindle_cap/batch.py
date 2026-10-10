"""ライブラリの全書籍を順に開いて撮影する一括ループ (kindle-cap-all).

AX / 撮影の実体は callable で受け取る。1 冊失敗しても次へ進み、
終わりに結果一覧を返す。既に `<out>/<name>.pdf` がある本は飛ばすので、
中断しても再実行すれば続きから進む。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .library import Book, safe_name
from .reader import Status

logger = logging.getLogger(__name__)

SKIP_EXISTING = "既存 PDF あり"
SKIP_SAMPLE = "サンプル"  # 書籍情報シートが割り込むなど挙動が違うので常に対象外
SKIP_PDF = "PDF"
SKIP_SERIES = "シリーズ (巻一覧)"  # 漫画などのシリーズは方針として対象外 (対応予定なし)


@dataclass(frozen=True)
class BookResult:
    book: Book
    name: str
    status: str  # captured / skipped / failed
    reason: str | None = None
    error: str | None = None


def select_books(
    books: list[Book],
    *,
    out: Path,
    include_pdf: bool,
    only: str | None,
) -> list[tuple[Book, str, str | None]]:
    """(book, 出力名, スキップ理由 or None) を表示順に返す。`only` はタイトルの部分一致."""
    selected: list[tuple[Book, str, str | None]] = []
    for book in books:
        if only is not None and only not in book.title:
            continue
        name = safe_name(book.title)
        reason: str | None = None
        if (out / f"{name}.pdf").exists():
            reason = SKIP_EXISTING
        elif book.is_sample:
            reason = SKIP_SAMPLE
        elif book.is_pdf and not include_pdf:
            reason = SKIP_PDF
        elif book.is_series:
            reason = SKIP_SERIES
        selected.append((book, name, reason))
    return selected


def run_all(
    books: list[Book],
    *,
    out: Path,
    include_pdf: bool,
    only: str | None,
    limit: int | None,
    open_book: Callable[[Book], None],
    close_book: Callable[[], None],
    capture_book: Callable[[Book, str], None],
    save_position: Callable[[], Status | None] | None = None,
    restore_position: Callable[[Status | None], None] | None = None,
) -> list[BookResult]:
    """選ばれた本を順に open → (位置記録) → capture → (位置復元) → close する.

    `save_position` / `restore_position` を渡すと、開いた直後の読書位置を記録し、
    撮影の後 (撮影が失敗しても) close の前に戻す。復元の失敗は警告にとどめ、
    撮影結果は失わない。"""
    results: list[BookResult] = []
    done = 0
    for book, name, reason in select_books(books, out=out, include_pdf=include_pdf, only=only):
        if reason is not None:
            logger.info("skip (%s): %s", reason, book.title)
            results.append(BookResult(book, name, "skipped", reason=reason))
            continue
        if limit is not None and done >= limit:
            break
        done += 1
        logger.info("=== [%d] %s ===", done, book.title)
        try:
            open_book(book)
            try:
                saved = save_position() if save_position is not None else None
                try:
                    capture_book(book, name)
                finally:
                    if restore_position is not None:
                        _restore_quietly(restore_position, saved, book)
            finally:
                close_book()
        except Exception as e:
            logger.exception("失敗: %s", book.title)
            results.append(BookResult(book, name, "failed", error=str(e)))
            continue
        results.append(BookResult(book, name, "captured"))
    return results


def _restore_quietly(
    restore_position: Callable[[Status | None], None], saved: Status | None, book: Book
) -> None:
    try:
        restore_position(saved)
    except Exception as e:
        logger.warning("読書位置を戻せませんでした (撮影結果は残します): %s: %s", book.title, e)
