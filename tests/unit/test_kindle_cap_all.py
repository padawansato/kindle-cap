"""kindle-cap-all (ライブラリ全書籍の一括キャプチャ) のテスト.

Kindle.app の AX ツリーに触る部分は差し替え可能な callable にしてあるので、
ここでは AX の生文字列の解釈・先頭移動の判断・一括ループの進行を偽物で検証する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from kindle_cap.batch import BookResult, run_all, select_books
from kindle_cap.config import Direction
from kindle_cap.library import Book, parse_book, safe_name
from kindle_cap.reader import KEY_LEFT, KEY_RIGHT, parse_status, rewind_to_start

# ---------------------------------------------------------------------------
# AX の生文字列 → Book
# ---------------------------------------------------------------------------


def test_parse_book_reads_title_author_tags_and_download_state() -> None:
    """ライブラリのボタン description / value は実機で観測した形そのまま。"""
    b = parse_book(
        "仮説思考―ＢＣＧ流　問題発見・解決の発想法 内田和成の思考, 内田 和成, NEW, ",
        "本がダウンロードされました。読書は1パーセント完了しています",
    )
    assert (b.title, b.author, b.tags) == (
        "仮説思考―ＢＣＧ流　問題発見・解決の発想法 内田和成の思考",
        "内田 和成",
        ("NEW",),
    )
    assert b.downloaded is True and b.progress_pct == 1

    sample = parse_book(
        "ひらいて（新潮文庫）, 綿矢 りさ, サンプル, ", "本はダウンロードされていません"
    )
    assert sample.is_sample and not sample.downloaded and sample.progress_pct is None

    pdf = parse_book(
        "oreilly-リーダブルコード, Dustin Boswell、Trevor Foucher　著、角 征典　訳, PDF, ",
        "本がダウンロードされました。",
    )
    assert pdf.is_pdf and pdf.author == "Dustin Boswell、Trevor Foucher　著、角 征典　訳"

    plain = parse_book("変な地図, 雨穴, ", None)
    assert plain.tags == () and not plain.is_sample and not plain.is_pdf

    western = parse_book(
        "The Technological Republic (English Edition), Karp, Alexander C.; Zamiska, Nicholas W., Prime Reading, ",
        None,
    )
    assert western.title == "The Technological Republic (English Edition)"
    assert western.author == "Karp, Alexander C.; Zamiska, Nicholas W."
    assert western.tags == ("Prime Reading",)


def test_safe_name_is_a_valid_single_path_component() -> None:
    assert safe_name("達人に学ぶDB設計 徹底指南書") == "達人に学ぶDB設計 徹底指南書"
    assert "/" not in safe_name("AI/ML 入門: 基礎/応用")
    assert safe_name("  ..  ") not in ("", ".", "..")
    assert len(safe_name("あ" * 300)) <= 80


# ---------------------------------------------------------------------------
# リーダー: ステータス文と先頭移動
# ---------------------------------------------------------------------------


def test_parse_status_extracts_total_and_current_page() -> None:
    assert parse_status("323ページ中の3ページ目 · 章を読み終えるまで:1分 · 1% · はじめに") == (
        323,
        3,
    )
    assert parse_status("444ページ中の207ページ目") == (444, 207)
    assert parse_status("位置No. 24/30 · 82%") == (30, 24)  # 小説などは位置番号表示
    assert parse_status(None) is None
    assert parse_status("表紙") is None


@dataclass
class FakeReader:
    """ページ送りキーで位置が動く偽の本。表紙 (index 0) はステータス文を持たない。"""

    n_pages: int
    next_key: int  # 「次のページ」に対応するキー (RTL なら右、LTR なら左)
    pos: int
    status_on_cover: bool = False
    presses: list[int] = field(default_factory=list)

    def press(self, key: int) -> None:
        self.presses.append(key)
        step = 1 if key == self.next_key else -1
        self.pos = min(self.n_pages - 1, max(0, self.pos + step))

    def page_hash(self) -> str:
        return f"page-{self.pos}"

    def read_status(self) -> tuple[int, int] | None:
        if self.pos == 0 and not self.status_on_cover:
            return None
        return (self.n_pages, self.pos + 1)


@pytest.mark.parametrize(
    ("next_key", "start", "expected"),
    [
        (KEY_RIGHT, 150, Direction.RTL),  # 右綴じ、途中から
        (KEY_LEFT, 150, Direction.LTR),  # 左綴じ、途中から
        (KEY_LEFT, 0, Direction.LTR),  # 左綴じ、表紙から (左 = 次 なので進んでしまう側)
        (KEY_RIGHT, 299, Direction.RTL),  # 右綴じ、末尾から
        (KEY_RIGHT, 0, Direction.RTL),  # 右綴じ、表紙から
    ],
)
def test_rewind_to_start_reaches_cover_and_reports_direction(
    next_key: int, start: int, expected: Direction
) -> None:
    book = FakeReader(n_pages=300, next_key=next_key, pos=start)
    direction = rewind_to_start(
        press=book.press,
        page_hash=book.page_hash,
        read_status=book.read_status,
        sleeper=lambda _: None,
        wait=0.0,
    )
    assert (book.pos, direction) == (0, expected)
    # 位置が分かる本では全ページを往復しない (ステータス文で前後を判断する)
    assert len(book.presses) <= start + 5


def test_rewind_to_start_gives_up_when_screen_never_settles() -> None:
    """アニメーションや再描画で画面が変わり続けるとき、無限に押し続けない。"""
    counter = iter(range(10**6))
    with pytest.raises(RuntimeError, match="先頭"):
        rewind_to_start(
            press=lambda _key: None,
            page_hash=lambda: f"frame-{next(counter)}",
            read_status=lambda: (10, 6),
            sleeper=lambda _: None,
            wait=0.0,
            max_presses=20,
        )


# ---------------------------------------------------------------------------
# 一括ループ
# ---------------------------------------------------------------------------


def _book(title: str, *tags: str, downloaded: bool = True) -> Book:
    return parse_book(
        f"{title}, 著者, {''.join(t + ', ' for t in tags)}",
        "本がダウンロードされました。" if downloaded else "本はダウンロードされていません",
    )


def test_select_books_skips_existing_samples_pdfs_and_applies_filter(tmp_path: Path) -> None:
    (tmp_path / "既存の本.pdf").write_bytes(b"%PDF")
    books = [
        _book("既存の本"),
        _book("サンプル本", "サンプル"),
        _book("自前PDF", "PDF"),
        _book("新しい本", "NEW"),
        _book("別の本"),
    ]
    selected = select_books(books, out=tmp_path, include_pdf=False, only=None)
    assert [(b.title, reason) for b, _, reason in selected] == [
        ("既存の本", "既存 PDF あり"),
        ("サンプル本", "サンプル"),
        ("自前PDF", "PDF"),
        ("新しい本", None),
        ("別の本", None),
    ]
    only = select_books(books, out=tmp_path, include_pdf=True, only="本")
    assert [b.title for b, _, reason in only if reason is None] == ["新しい本", "別の本"]


def test_run_all_continues_after_a_failure_and_always_closes_the_book(tmp_path: Path) -> None:
    books = [_book("壊れる本"), _book("うまくいく本")]
    log: list[str] = []

    def open_book(b: Book) -> None:
        log.append(f"open:{b.title}")

    def close_book() -> None:
        log.append("close")

    def capture_book(b: Book, name: str) -> None:
        log.append(f"capture:{name}")
        if b.title == "壊れる本":
            raise RuntimeError("撮影に失敗")

    results = run_all(
        books,
        out=tmp_path,
        include_pdf=False,
        only=None,
        limit=None,
        open_book=open_book,
        close_book=close_book,
        capture_book=capture_book,
    )
    assert [(r.book.title, r.status) for r in results] == [
        ("壊れる本", "failed"),
        ("うまくいく本", "captured"),
    ]
    assert results[0].error == "撮影に失敗"
    assert log == [
        "open:壊れる本",
        "capture:壊れる本",
        "close",
        "open:うまくいく本",
        "capture:うまくいく本",
        "close",
    ]
    assert isinstance(results[0], BookResult)


# ---------------------------------------------------------------------------
# dismiss_sheet (issue #86): 読書位置の同期シートは Escape で、書籍情報シートは AXPress で閉じる
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("buttons", "expect_escape", "expect_press", "expect_result"),
    [
        # 同期シート: ハンドル「閉じる」+「最新の位置に移動」。AXPress は効かず Escape で消える
        (["閉じる", "最新の位置に移動"], True, False, True),
        (["閉じる", "位置182に戻る"], True, False, True),
        # 書籍情報シート (サンプル): 従来どおり「閉じる」を AXPress
        (["閉じる", "シェア"], False, True, True),
        ([], False, False, False),
    ],
)
def test_dismiss_sheet_uses_escape_for_sync_sheet_and_press_for_info_sheet(
    monkeypatch: pytest.MonkeyPatch,
    buttons: list[str],
    expect_escape: bool,
    expect_press: bool,
    expect_result: bool,
) -> None:
    from kindle_cap import library

    class FakeEl:
        def __init__(self, desc: str) -> None:
            self.desc = desc

    def fake_find(app: object, role: str, pred: object) -> list[FakeEl]:
        assert role == "AXButton"
        return [FakeEl(d) for d in buttons if pred(d)]  # type: ignore[operator]

    pressed: list[str] = []
    keys: list[int] = []
    monkeypatch.setattr(library.ax, "find", fake_find)
    monkeypatch.setattr(library.ax, "description", lambda el: el.desc)
    monkeypatch.setattr(library.ax, "perform", lambda el, action: pressed.append(el.desc))
    monkeypatch.setattr(library, "post_key", lambda code: keys.append(code))
    monkeypatch.setattr(library.time, "sleep", lambda s: None)

    assert library.dismiss_sheet(object()) is expect_result
    assert (keys == [53]) is expect_escape
    assert (pressed == ["閉じる"]) is expect_press
