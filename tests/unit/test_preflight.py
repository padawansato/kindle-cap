import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.config import Direction, Geometry
from kindle_cap.preflight import (
    PreflightError,
    _is_accessibility_error,
    _parse_count,
    detect_direction,
    preflight,
)

# ---------------------------------------------------------------------------
# 純粋関数 _parse_count: "1\n" → 1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("0", 0),
        ("1", 1),
        ("10", 10),
        ("999", 999),
        ("0\n", 0),
        ("1\n", 1),
        (" 5 ", 5),
        ("\n5\n", 5),
    ],
)
def test_parse_count_extracts_integer(text: str, expected: int) -> None:
    assert _parse_count(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "1.5", "one", "  ", "\n\n"])
def test_parse_count_rejects_non_integer(text: str) -> None:
    with pytest.raises(ValueError):
        _parse_count(text)


# ---------------------------------------------------------------------------
# 純粋関数 _is_accessibility_error: stderr 文字列 → 権限エラーか判定
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stderr",
    [
        "error: -1719 (not authorized)",
        "execution error: -1719",
        "Some prefix -1719 some suffix",
        "not allowed assistive access",
        "Application is not allowed assistive access",
    ],
)
def test_is_accessibility_error_recognizes_known_patterns(stderr: str) -> None:
    assert _is_accessibility_error(stderr) is True


@pytest.mark.parametrize(
    "stderr",
    [
        "",
        "Some other error",
        "syntax error",
        "process not found",
        "-1718",  # 似た番号
        "1719",  # マイナスなし
    ],
)
def test_is_accessibility_error_returns_false_for_other_errors(stderr: str) -> None:
    assert _is_accessibility_error(stderr) is False


def test_is_accessibility_error_handles_none_safely() -> None:
    """stderr が None を渡されても True/False を返すべき"""
    assert _is_accessibility_error(None) is False


# ---------------------------------------------------------------------------
# preflight: シーケンスを subprocess mock で検証
# 各シナリオごとに 1 つずつ
# ---------------------------------------------------------------------------


def _run_factory(outputs: list):
    """outputs は呼び出し順に返す stdout (str) または raise する例外のリスト"""
    iterator = iter(outputs)

    def _run(*args, **kwargs):
        item = next(iterator)
        if isinstance(item, BaseException):
            raise item
        return MagicMock(stdout=item)

    return _run


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_passes_when_all_ok(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["1\n", "1\n", "Finder\n"])
    preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_kindle_not_running(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["0\n"])
    with pytest.raises(PreflightError, match="Kindle"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_no_window(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["1\n", "0\n"])
    with pytest.raises(PreflightError, match="ウィンドウ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_accessibility_denied_with_dash_1719(
    mock_run: MagicMock,
) -> None:
    err = subprocess.CalledProcessError(1, "osascript", stderr="error -1719: Not authorized")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(PreflightError, match="アクセシビリティ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_raises_when_accessibility_denied_with_text_pattern(
    mock_run: MagicMock,
) -> None:
    err = subprocess.CalledProcessError(1, "osascript", stderr="not allowed assistive access")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(PreflightError, match="アクセシビリティ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_propagates_unknown_subprocess_error(mock_run: MagicMock) -> None:
    err = subprocess.CalledProcessError(2, "osascript", stderr="something else")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(subprocess.CalledProcessError):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_calls_three_subprocesses_when_all_ok(mock_run: MagicMock) -> None:
    mock_run.side_effect = _run_factory(["1\n", "1\n", "Finder\n"])
    preflight()
    assert mock_run.call_count == 3


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_short_circuits_on_kindle_missing(mock_run: MagicMock) -> None:
    """Kindle 未起動なら、後続の osascript は呼ばれないこと"""
    mock_run.side_effect = _run_factory(["0\n"])
    with pytest.raises(PreflightError):
        preflight()
    assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# detect_direction: 表紙起点での方向自動判定
# capturer は呼び出し順に異なるバイト列を path に書き出す stub を渡す
# 順序は (origin) → (probe1, probe2, probe3) → (verify) の最大 5 回
# ---------------------------------------------------------------------------


def _capturer_writing_seq(seq: list[bytes]) -> Callable[[Geometry, Path], None]:
    """呼び出し順に seq[i] を path に書き込む stub。"""
    counter = {"n": 0}

    def _cap(geom: Geometry, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(seq[counter["n"]])
        counter["n"] += 1

    return _cap


def _detect_kwargs(tmp_path: Path, **overrides):
    base = dict(
        out_dir=tmp_path,
        geom_provider=lambda: Geometry(0, 0, 100, 100),
        activator=lambda: None,
        sender=MagicMock(),
        sleeper=lambda _s: None,
        wait=0.0,
    )
    base.update(overrides)
    return base


def test_detect_direction_returns_probe_direction_when_pages_advance(
    tmp_path: Path,
) -> None:
    """起点 != 試写3 のシーケンス → probe_direction (RTL) を返し、試写を本番採用"""
    cap = _capturer_writing_seq([b"origin", b"p1", b"p2", b"p3"])
    direction, pngs = detect_direction(**_detect_kwargs(tmp_path, capturer=cap))
    assert direction is Direction.RTL
    assert [p.name for p in pngs] == ["page_001.png", "page_002.png", "page_003.png"]
    assert all(p.exists() for p in pngs)


def test_detect_direction_returns_probe_pngs_named_page_001_to_003(
    tmp_path: Path,
) -> None:
    cap = _capturer_writing_seq([b"o", b"a", b"b", b"c"])
    _, pngs = detect_direction(**_detect_kwargs(tmp_path, capturer=cap))
    assert pngs[0] == tmp_path / "page_001.png"
    assert pngs[1] == tmp_path / "page_002.png"
    assert pngs[2] == tmp_path / "page_003.png"


def test_detect_direction_unlinks_origin_png_on_success(tmp_path: Path) -> None:
    cap = _capturer_writing_seq([b"o", b"a", b"b", b"c"])
    detect_direction(**_detect_kwargs(tmp_path, capturer=cap))
    assert not (tmp_path / "_origin.png").exists()


def test_detect_direction_calls_sender_three_times_for_probe(tmp_path: Path) -> None:
    cap = _capturer_writing_seq([b"o", b"a", b"b", b"c"])
    sender = MagicMock()
    detect_direction(**_detect_kwargs(tmp_path, capturer=cap, sender=sender))
    assert sender.call_count == 3
    assert all(c.args[0] is Direction.RTL for c in sender.call_args_list)


def test_detect_direction_default_probe_direction_is_rtl(tmp_path: Path) -> None:
    cap = _capturer_writing_seq([b"o", b"a", b"b", b"c"])
    direction, _ = detect_direction(**_detect_kwargs(tmp_path, capturer=cap))
    assert direction is Direction.RTL


def test_detect_direction_uses_probe_count_parameter(tmp_path: Path) -> None:
    """probe_count=5 を渡せば 5 枚撮る。"""
    cap = _capturer_writing_seq([b"o", b"1", b"2", b"3", b"4", b"5"])
    sender = MagicMock()
    direction, pngs = detect_direction(
        **_detect_kwargs(tmp_path, capturer=cap, sender=sender),
        probe_count=5,
    )
    assert direction is Direction.RTL
    assert len(pngs) == 5
    assert sender.call_count == 5


def test_detect_direction_falls_back_to_other_direction_when_no_advance(
    tmp_path: Path,
) -> None:
    """起点 == 試写3（無反応）、verify では変化あり → other_direction を返し試写は破棄。"""
    cap = _capturer_writing_seq([b"same", b"same", b"same", b"same", b"changed"])
    sender = MagicMock()
    direction, pngs = detect_direction(
        **_detect_kwargs(tmp_path, capturer=cap, sender=sender),
    )
    assert direction is Direction.LTR
    assert pngs == []
    assert sender.call_args_list[-1].args[0] is Direction.LTR


def test_detect_direction_unlinks_probe_pngs_on_fallback(tmp_path: Path) -> None:
    """fallback 時、試写 PNG / _origin / _verify がすべて削除される。"""
    cap = _capturer_writing_seq([b"same", b"same", b"same", b"same", b"changed"])
    detect_direction(**_detect_kwargs(tmp_path, capturer=cap))
    assert not (tmp_path / "page_001.png").exists()
    assert not (tmp_path / "page_002.png").exists()
    assert not (tmp_path / "page_003.png").exists()
    assert not (tmp_path / "_origin.png").exists()
    assert not (tmp_path / "_verify.png").exists()
