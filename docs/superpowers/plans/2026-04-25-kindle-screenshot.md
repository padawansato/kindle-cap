# Kindle Screenshot Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** macOS の Amazon Kindle アプリの表示中ページを連続キャプチャし、無劣化のまま単一 PDF にまとめる CLI ツールを TDD で構築する。

**Architecture:** typer CLI が CaptureConfig を構築 → orchestrator がループ制御 → window/capture/keys/preflight モジュールが macOS 標準コマンド (osascript/screencapture) を subprocess 経由で呼ぶ → pdf モジュールが img2pdf で結合。各モジュールは単一責務で、subprocess.run を mock したユニットテストで検証可能。

**Tech Stack:** Python 3.12+, uv, typer, img2pdf, pytest, pypdf (test only), Pillow (test only)

**Reference Spec:** `docs/superpowers/specs/2026-04-25-kindle-screenshot-design.md`

---

## File Structure

| ファイル | 責務 |
|---|---|
| `pyproject.toml` | uv プロジェクト定義、依存、エントリーポイント、pytest 設定 |
| `.gitignore` | Python の生成物、出力ディレクトリ、実験ディレクトリを除外 |
| `src/kindle_cap/__init__.py` | パッケージマーカー |
| `src/kindle_cap/config.py` | `Direction` (StrEnum), `Geometry`, `CaptureConfig` (dataclass + validation) |
| `src/kindle_cap/pdf.py` | `build_pdf(png_paths, out_path)` — img2pdf による結合 |
| `src/kindle_cap/window.py` | `activate_kindle()`, `get_window_geometry()` — osascript ラッパー |
| `src/kindle_cap/capture.py` | `capture_rect(geom, out_path)` — screencapture ラッパー |
| `src/kindle_cap/keys.py` | `send_next_page(direction)` — 矢印キー送信 |
| `src/kindle_cap/preflight.py` | `preflight()` — Kindle 起動／ウィンドウ／アクセシビリティ権限の確認 |
| `src/kindle_cap/orchestrator.py` | `run(config, dry_run=False)` — 撮影ループ／中断処理／PDF 生成 |
| `src/kindle_cap/cli.py` | `capture()`, `rebuild_pdf()` の typer コマンドと entry point 関数 |
| `tests/conftest.py` | `live` マーカーをデフォルトで skip する仕組み |
| `tests/unit/test_*.py` | 各モジュールのユニットテスト |
| `tests/integration/test_real_capture.py` | `@pytest.mark.live` の手動 integration |

---

## Task 0: プロジェクト初期化

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/kindle_cap/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: `pyproject.toml` を作成**

```toml
[project]
name = "kindle-cap"
version = "0.1.0"
description = "Capture Kindle for Mac pages into a single PDF"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.16",
    "img2pdf>=0.5",
]

[project.scripts]
kindle-cap = "kindle_cap.cli:run_capture"
kindle-cap-pdf = "kindle_cap.cli:run_rebuild_pdf"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pypdf>=4.0",
    "pillow>=10.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "live: requires Kindle.app running with a book on the first page",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/kindle_cap"]
```

- [ ] **Step 2: `.gitignore` を作成**

```
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
*.egg-info/
.venv/
venv/

# Build
build/
dist/

# Project
output/
experiments/
```

- [ ] **Step 3: パッケージとテストの空ファイルを作成**

```python
# src/kindle_cap/__init__.py
"""Capture Kindle for Mac pages into a single PDF."""
__version__ = "0.1.0"
```

```python
# tests/__init__.py
```

```python
# tests/unit/__init__.py
```

```python
# tests/integration/__init__.py
```

- [ ] **Step 4: `tests/conftest.py` を作成（`live` マーカーをデフォルトで skip）**

```python
import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("-m", default=""):
        return
    skip_live = pytest.mark.skip(reason="needs Kindle running; use `pytest -m live`")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
```

- [ ] **Step 5: 依存解決と動作確認**

Run: `uv sync`
Expected: `Resolved N packages` のような出力。エラーなく完了

Run: `uv run pytest`
Expected: `no tests ran` または `collected 0 items`（テストはまだないので）

- [ ] **Step 6: コミット**

```bash
git add pyproject.toml .gitignore src/kindle_cap/__init__.py tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/conftest.py
git commit -m "chore: uv プロジェクトとテスト基盤を初期化"
```

---

## Task 1: config.py — Direction / Geometry / CaptureConfig

**Files:**
- Create: `src/kindle_cap/config.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_config.py
from pathlib import Path

import pytest

from kindle_cap.config import CaptureConfig, Direction, Geometry


def test_direction_string_values():
    assert Direction.RTL == "rtl"
    assert Direction.LTR == "ltr"


def test_geometry_holds_values():
    g = Geometry(x=0, y=31, width=1440, height=869)
    assert g.x == 0
    assert g.y == 31
    assert g.width == 1440
    assert g.height == 869


def test_geometry_is_frozen():
    g = Geometry(x=0, y=0, width=100, height=100)
    with pytest.raises(Exception):
        g.x = 99  # type: ignore[misc]


def _valid_config_kwargs(**overrides):
    base = dict(
        name="my-book",
        pages=10,
        direction=Direction.RTL,
        wait=1.0,
        out=Path("output"),
        keep_png=True,
    )
    base.update(overrides)
    return base


def test_config_constructs_with_valid_values():
    c = CaptureConfig(**_valid_config_kwargs())
    assert c.name == "my-book"
    assert c.pages == 10
    assert c.direction is Direction.RTL


def test_config_pages_zero_rejected():
    with pytest.raises(ValueError, match="pages"):
        CaptureConfig(**_valid_config_kwargs(pages=0))


def test_config_pages_negative_rejected():
    with pytest.raises(ValueError, match="pages"):
        CaptureConfig(**_valid_config_kwargs(pages=-3))


def test_config_wait_negative_rejected():
    with pytest.raises(ValueError, match="wait"):
        CaptureConfig(**_valid_config_kwargs(wait=-0.5))


def test_config_wait_zero_allowed():
    c = CaptureConfig(**_valid_config_kwargs(wait=0))
    assert c.wait == 0


def test_config_empty_name_rejected():
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name=""))


def test_config_slash_in_name_rejected():
    with pytest.raises(ValueError, match="name"):
        CaptureConfig(**_valid_config_kwargs(name="path/with/slash"))
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'kindle_cap.config'`

- [ ] **Step 3: `src/kindle_cap/config.py` を実装**

```python
"""Configuration data classes for kindle_cap."""
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Direction(StrEnum):
    RTL = "rtl"
    LTR = "ltr"


@dataclass(frozen=True)
class Geometry:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class CaptureConfig:
    name: str
    pages: int
    direction: Direction
    wait: float
    out: Path
    keep_png: bool

    def __post_init__(self) -> None:
        if self.pages <= 0:
            raise ValueError("pages must be positive")
        if self.wait < 0:
            raise ValueError("wait must be non-negative")
        if not self.name:
            raise ValueError("name must be non-empty")
        if "/" in self.name:
            raise ValueError("name must not contain '/'")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: 全 9 テスト pass

- [ ] **Step 5: コミット**

```bash
git add src/kindle_cap/config.py tests/unit/test_config.py
git commit -m "feat(config): CaptureConfig / Direction / Geometry を追加"
```

---

## Task 2: pdf.py — img2pdf で PNG 群を結合

**Files:**
- Create: `src/kindle_cap/pdf.py`
- Test: `tests/unit/test_pdf.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_pdf.py
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from kindle_cap.pdf import build_pdf


@pytest.fixture
def sample_pngs(tmp_path: Path) -> list[Path]:
    paths = []
    for i, color in enumerate(["red", "green", "blue"], 1):
        p = tmp_path / f"page_{i:03d}.png"
        Image.new("RGB", (200, 300), color).save(p)
        paths.append(p)
    return paths


def test_build_pdf_creates_pdf_file(sample_pngs: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    build_pdf(sample_pngs, out)
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_build_pdf_has_three_pages(sample_pngs: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    build_pdf(sample_pngs, out)
    reader = PdfReader(str(out))
    assert len(reader.pages) == 3


def test_build_pdf_creates_parent_dirs(sample_pngs: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deep" / "out.pdf"
    build_pdf(sample_pngs, out)
    assert out.exists()


def test_build_pdf_empty_list_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        build_pdf([], tmp_path / "o.pdf")
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_pdf.py -v`
Expected: `ModuleNotFoundError: No module named 'kindle_cap.pdf'`

- [ ] **Step 3: `src/kindle_cap/pdf.py` を実装**

```python
"""Combine PNG images into a single PDF using img2pdf (lossless)."""
from pathlib import Path

import img2pdf


def build_pdf(png_paths: list[Path], out_path: Path) -> None:
    if not png_paths:
        raise ValueError("png_paths must not be empty")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = img2pdf.convert([str(p) for p in png_paths])
    out_path.write_bytes(pdf_bytes)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_pdf.py -v`
Expected: 全 4 テスト pass

- [ ] **Step 5: コミット**

```bash
git add src/kindle_cap/pdf.py tests/unit/test_pdf.py
git commit -m "feat(pdf): img2pdf による無劣化 PDF 結合を追加"
```

---

## Task 3: window.py — Kindle のウィンドウ位置取得と前面化

**Files:**
- Create: `src/kindle_cap/window.py`
- Test: `tests/unit/test_window.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_window.py
from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.config import Geometry
from kindle_cap.window import activate_kindle, get_window_geometry


@patch("kindle_cap.window.subprocess.run")
def test_activate_kindle_calls_osascript(mock_run: MagicMock) -> None:
    activate_kindle()
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "osascript"
    assert cmd[1] == "-e"
    assert "Amazon Kindle" in cmd[2]
    assert "activate" in cmd[2]
    assert kwargs.get("check") is True


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_parses_newline_output(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="0\n31\n1440\n869\n")
    g = get_window_geometry()
    assert g == Geometry(x=0, y=31, width=1440, height=869)


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_targets_kindle_process(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="0\n0\n100\n100\n")
    get_window_geometry()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert "Kindle" in cmd[2]


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_unexpected_output_raises(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="garbage\n")
    with pytest.raises(RuntimeError, match="output"):
        get_window_geometry()


@patch("kindle_cap.window.subprocess.run")
def test_get_window_geometry_partial_output_raises(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout="1\n2\n")
    with pytest.raises(RuntimeError):
        get_window_geometry()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_window.py -v`
Expected: `ModuleNotFoundError: No module named 'kindle_cap.window'`

- [ ] **Step 3: `src/kindle_cap/window.py` を実装**

```python
"""Activate the Kindle app and read its window geometry via AppleScript."""
import subprocess

from .config import Geometry

_ACTIVATE_SCRIPT = 'tell application "Amazon Kindle" to activate'

_GEOMETRY_SCRIPT = """tell application "System Events" to tell process "Kindle"
  set w to window 1
  set pos to position of w
  set sz to size of w
  return ((item 1 of pos) as string) & linefeed & ((item 2 of pos) as string) & linefeed & ((item 1 of sz) as string) & linefeed & ((item 2 of sz) as string)
end tell"""


def activate_kindle() -> None:
    subprocess.run(
        ["osascript", "-e", _ACTIVATE_SCRIPT],
        check=True,
    )


def get_window_geometry() -> Geometry:
    result = subprocess.run(
        ["osascript", "-e", _GEOMETRY_SCRIPT],
        check=True,
        capture_output=True,
        text=True,
    )
    parts = result.stdout.strip().split("\n")
    if len(parts) != 4:
        raise RuntimeError(f"unexpected osascript output: {result.stdout!r}")
    try:
        x, y, w, h = (int(p.strip()) for p in parts)
    except ValueError as e:
        raise RuntimeError(f"could not parse osascript output: {result.stdout!r}") from e
    return Geometry(x=x, y=y, width=w, height=h)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_window.py -v`
Expected: 全 5 テスト pass

- [ ] **Step 5: コミット**

```bash
git add src/kindle_cap/window.py tests/unit/test_window.py
git commit -m "feat(window): Kindle ウィンドウの activate と位置取得を追加"
```

---

## Task 4: capture.py — screencapture で範囲キャプチャ

**Files:**
- Create: `src/kindle_cap/capture.py`
- Test: `tests/unit/test_capture.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_capture.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from kindle_cap.capture import capture_rect
from kindle_cap.config import Geometry


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_invokes_screencapture(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=31, width=1440, height=869)
    out = tmp_path / "page.png"
    capture_rect(geom, out)
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "screencapture"
    assert kwargs.get("check") is True


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_correct_R_argument(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=10, y=20, width=300, height=400)
    out = tmp_path / "p.png"
    capture_rect(geom, out)
    cmd = mock_run.call_args[0][0]
    r_index = cmd.index("-R")
    assert cmd[r_index + 1] == "10,20,300,400"


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_silent_flag(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=0, width=100, height=100)
    capture_rect(geom, tmp_path / "p.png")
    cmd = mock_run.call_args[0][0]
    assert "-x" in cmd


@patch("kindle_cap.capture.subprocess.run")
def test_capture_rect_passes_output_path(mock_run: MagicMock, tmp_path: Path) -> None:
    geom = Geometry(x=0, y=0, width=100, height=100)
    out = tmp_path / "p.png"
    capture_rect(geom, out)
    cmd = mock_run.call_args[0][0]
    assert str(out) in cmd
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_capture.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: `src/kindle_cap/capture.py` を実装**

```python
"""Capture a screen rectangle using macOS screencapture."""
import subprocess
from pathlib import Path

from .config import Geometry


def capture_rect(geom: Geometry, out_path: Path) -> None:
    rect = f"{geom.x},{geom.y},{geom.width},{geom.height}"
    subprocess.run(
        ["screencapture", "-R", rect, "-x", str(out_path)],
        check=True,
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_capture.py -v`
Expected: 全 4 テスト pass

- [ ] **Step 5: コミット**

```bash
git add src/kindle_cap/capture.py tests/unit/test_capture.py
git commit -m "feat(capture): screencapture による範囲キャプチャを追加"
```

---

## Task 5: keys.py — 矢印キー送信

**Files:**
- Create: `src/kindle_cap/keys.py`
- Test: `tests/unit/test_keys.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_keys.py
from unittest.mock import MagicMock, patch

from kindle_cap.config import Direction
from kindle_cap.keys import send_next_page


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_rtl_sends_right_arrow(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "osascript"
    assert "key code 124" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_ltr_sends_left_arrow(mock_run: MagicMock) -> None:
    send_next_page(Direction.LTR)
    cmd = mock_run.call_args[0][0]
    assert "key code 123" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_targets_kindle_process(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    cmd = mock_run.call_args[0][0]
    assert "Kindle" in cmd[2]


@patch("kindle_cap.keys.subprocess.run")
def test_send_next_page_uses_check_true(mock_run: MagicMock) -> None:
    send_next_page(Direction.RTL)
    assert mock_run.call_args.kwargs.get("check") is True
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_keys.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: `src/kindle_cap/keys.py` を実装**

```python
"""Send arrow-key presses to the Kindle process via System Events."""
import subprocess

from .config import Direction

_KEY_RIGHT = 124
_KEY_LEFT = 123


def send_next_page(direction: Direction) -> None:
    key_code = _KEY_RIGHT if direction is Direction.RTL else _KEY_LEFT
    script = (
        f'tell application "System Events" to tell process "Kindle" '
        f'to key code {key_code}'
    )
    subprocess.run(
        ["osascript", "-e", script],
        check=True,
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_keys.py -v`
Expected: 全 4 テスト pass

- [ ] **Step 5: コミット**

```bash
git add src/kindle_cap/keys.py tests/unit/test_keys.py
git commit -m "feat(keys): direction 別の次ページキー送信を追加"
```

---

## Task 6: preflight.py — 起動前チェック

**Files:**
- Create: `src/kindle_cap/preflight.py`
- Test: `tests/unit/test_preflight.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_preflight.py
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kindle_cap.preflight import PreflightError, preflight


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
def test_preflight_raises_when_accessibility_denied(mock_run: MagicMock) -> None:
    err = subprocess.CalledProcessError(1, "osascript", stderr="error -1719: Not authorized")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(PreflightError, match="アクセシビリティ"):
        preflight()


@patch("kindle_cap.preflight.subprocess.run")
def test_preflight_propagates_unknown_subprocess_error(mock_run: MagicMock) -> None:
    err = subprocess.CalledProcessError(2, "osascript", stderr="something else")
    mock_run.side_effect = _run_factory(["1\n", "1\n", err])
    with pytest.raises(subprocess.CalledProcessError):
        preflight()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_preflight.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: `src/kindle_cap/preflight.py` を実装**

```python
"""Validate prerequisites before starting the capture loop."""
import subprocess


class PreflightError(RuntimeError):
    pass


_COUNT_KINDLE_PROC = (
    'tell application "System Events" to '
    '(count (every process whose name is "Kindle"))'
)
_COUNT_KINDLE_WINDOWS = (
    'tell application "System Events" to '
    'tell process "Kindle" to (count windows)'
)
_ACCESSIBILITY_PROBE = (
    'tell application "System Events" to get name of first process'
)


def _run_oscript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _is_kindle_running() -> bool:
    return int(_run_oscript(_COUNT_KINDLE_PROC)) > 0


def _has_kindle_window() -> bool:
    return int(_run_oscript(_COUNT_KINDLE_WINDOWS)) > 0


def _can_send_keystrokes() -> bool:
    try:
        _run_oscript(_ACCESSIBILITY_PROBE)
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if "-1719" in stderr or "not allowed assistive access" in stderr:
            return False
        raise


def preflight() -> None:
    if not _is_kindle_running():
        raise PreflightError(
            "Kindle.app を起動してください（プロセスが見つかりません）"
        )
    if not _has_kindle_window():
        raise PreflightError("Kindle のウィンドウが開いていません")
    if not _can_send_keystrokes():
        raise PreflightError(
            "アクセシビリティ権限が付与されていません。\n"
            "システム設定 > プライバシーとセキュリティ > アクセシビリティ で\n"
            "ターミナル（iTerm2 等）に許可を与えてください。"
        )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_preflight.py -v`
Expected: 全 5 テスト pass

- [ ] **Step 5: コミット**

```bash
git add src/kindle_cap/preflight.py tests/unit/test_preflight.py
git commit -m "feat(preflight): Kindle 起動・ウィンドウ・権限の事前確認を追加"
```

---

## Task 7: orchestrator.py — 撮影ループと中断処理

**Files:**
- Create: `src/kindle_cap/orchestrator.py`
- Test: `tests/unit/test_orchestrator.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_orchestrator.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from kindle_cap.config import CaptureConfig, Direction, Geometry
from kindle_cap.orchestrator import run


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


_GEOM = Geometry(x=0, y=0, width=100, height=100)


def _patch_all(*, geom=_GEOM):
    """Decorator that mocks every external dependency in orchestrator."""
    def decorator(func):
        @patch("kindle_cap.orchestrator.build_pdf")
        @patch("kindle_cap.orchestrator.send_next_page")
        @patch("kindle_cap.orchestrator.capture_rect")
        @patch("kindle_cap.orchestrator.get_window_geometry", return_value=geom)
        @patch("kindle_cap.orchestrator.activate_kindle")
        @patch("kindle_cap.orchestrator.preflight")
        def wrapper(mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, *args, **kwargs):
            return func(mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, *args, **kwargs)
        return wrapper
    return decorator


@_patch_all()
def test_run_three_pages_calls_each_step_correctly(
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    run(_config(tmp_path, pages=3))
    assert mock_pre.call_count == 1
    assert mock_act.call_count == 3
    assert mock_geom.call_count == 3
    assert mock_cap.call_count == 3
    assert mock_send.call_count == 2  # 最終ページ後は送らない
    mock_pdf.assert_called_once()


@_patch_all()
def test_run_dry_run_takes_one_shot_and_skips_pdf(
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    run(_config(tmp_path), dry_run=True)
    assert mock_cap.call_count == 1
    assert mock_send.call_count == 0
    mock_pdf.assert_not_called()


@_patch_all()
def test_run_dry_run_writes_to_dry_run_png(
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    run(_config(tmp_path), dry_run=True)
    out_path = mock_cap.call_args[0][1]
    assert out_path.name == "dry_run.png"


@_patch_all()
def test_run_keyboard_interrupt_keeps_partial_and_skips_pdf(
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    mock_cap.side_effect = [None, KeyboardInterrupt(), None]
    run(_config(tmp_path, pages=5))
    mock_pdf.assert_not_called()


@_patch_all()
def test_run_deletes_existing_pngs_before_capture(
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    out_dir = tmp_path / "bk"
    out_dir.mkdir()
    stale = out_dir / "page_999.png"
    stale.write_bytes(b"old")
    run(_config(tmp_path, pages=2, name="bk"))
    assert not stale.exists()


@_patch_all()
def test_run_no_keep_png_removes_pngs_after_pdf(
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    # capture_rect を mock しているので PNG は実際には作られない。
    # orchestrator が「captured リスト」として保持したパスを unlink しようとする挙動を検証する。
    # 実ファイルが必要なので、capture_rect の side_effect で touch する。
    def touch(geom, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    mock_cap.side_effect = touch

    run(_config(tmp_path, pages=2, keep_png=False))
    assert not (tmp_path / "bk" / "page_001.png").exists()
    assert not (tmp_path / "bk" / "page_002.png").exists()


@_patch_all()
def test_run_writes_pdf_to_out_root(
    mock_pre, mock_act, mock_geom, mock_cap, mock_send, mock_pdf, tmp_path,
):
    run(_config(tmp_path, name="hello", pages=2))
    pdf_path = mock_pdf.call_args[0][1]
    assert pdf_path == tmp_path / "hello.pdf"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_orchestrator.py -v`
Expected: `ModuleNotFoundError: No module named 'kindle_cap.orchestrator'`

- [ ] **Step 3: `src/kindle_cap/orchestrator.py` を実装**

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_orchestrator.py -v`
Expected: 全 7 テスト pass

- [ ] **Step 5: コミット**

```bash
git add src/kindle_cap/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "feat(orchestrator): 撮影ループ・dry-run・中断処理を追加"
```

---

## Task 8: cli.py — typer ベースの CLI

**Files:**
- Create: `src/kindle_cap/cli.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_cli.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from kindle_cap.cli import capture, rebuild_pdf

runner = CliRunner()


def _make_app(func) -> typer.Typer:
    app = typer.Typer()
    app.command()(func)
    return app


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_with_all_flags(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name", "test-book",
            "--pages", "3",
            "--direction", "rtl",
            "--out", str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    config_arg = mock_run.call_args.args[0]
    assert config_arg.name == "test-book"
    assert config_arg.pages == 3
    assert config_arg.direction.value == "rtl"
    assert config_arg.out == tmp_path
    assert config_arg.wait == 1.0
    assert config_arg.keep_png is True


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_prompts_when_name_missing(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--pages", "3",
            "--direction", "rtl",
            "--out", str(tmp_path),
        ],
        input="prompted-name\n",
    )
    assert result.exit_code == 0, result.output
    config_arg = mock_run.call_args.args[0]
    assert config_arg.name == "prompted-name"


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_dry_run_passed_through(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name", "x",
            "--pages", "1",
            "--direction", "ltr",
            "--out", str(tmp_path),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs.get("dry_run") is True


@patch("kindle_cap.cli.orchestrator_run")
def test_capture_no_keep_png(mock_run: MagicMock, tmp_path: Path) -> None:
    app = _make_app(capture)
    result = runner.invoke(
        app,
        [
            "--name", "x",
            "--pages", "1",
            "--direction", "ltr",
            "--out", str(tmp_path),
            "--no-keep-png",
        ],
    )
    assert result.exit_code == 0, result.output
    assert mock_run.call_args.args[0].keep_png is False


@patch("kindle_cap.cli.build_pdf")
def test_rebuild_pdf_writes_to_parent_with_dir_name(
    mock_build: MagicMock, tmp_path: Path,
) -> None:
    book = tmp_path / "my-book"
    book.mkdir()
    (book / "page_001.png").write_bytes(b"a")
    (book / "page_002.png").write_bytes(b"b")

    app = _make_app(rebuild_pdf)
    result = runner.invoke(app, [str(book)])

    assert result.exit_code == 0, result.output
    pngs_arg, out_arg = mock_build.call_args.args
    assert out_arg == tmp_path / "my-book.pdf"
    assert [p.name for p in pngs_arg] == ["page_001.png", "page_002.png"]


def test_rebuild_pdf_missing_dir_exits_nonzero(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    app = _make_app(rebuild_pdf)
    result = runner.invoke(app, [str(missing)])
    assert result.exit_code != 0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: `src/kindle_cap/cli.py` を実装**

```python
"""Typer-based CLI entry points for kindle_cap."""
from pathlib import Path

import typer

from .config import CaptureConfig, Direction
from .orchestrator import run as orchestrator_run
from .pdf import build_pdf
from .preflight import PreflightError


def capture(
    pages: int = typer.Option(..., "--pages", help="撮影ページ数"),
    direction: Direction = typer.Option(
        ..., "--direction", help="rtl=右綴じ、ltr=左綴じ",
        case_sensitive=False,
    ),
    name: str = typer.Option(
        None, "--name",
        help="書籍名（出力ディレクトリ名）。未指定時はプロンプトで聞きます",
    ),
    wait: float = typer.Option(1.0, "--wait", help="ページ送り後の待機秒"),
    out: Path = typer.Option(Path("output"), "--out", help="出力先ディレクトリ"),
    keep_png: bool = typer.Option(
        True, "--keep-png/--no-keep-png", help="中間 PNG を保持",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="1 枚だけ撮影し PDF は作らない",
    ),
) -> None:
    if name is None:
        name = typer.prompt("書籍名 (出力ディレクトリ名)")
    config = CaptureConfig(
        name=name,
        pages=pages,
        direction=direction,
        wait=wait,
        out=out,
        keep_png=keep_png,
    )
    try:
        orchestrator_run(config, dry_run=dry_run)
    except PreflightError as e:
        typer.echo(f"[エラー] {e}", err=True)
        raise typer.Exit(code=1)


def rebuild_pdf(
    directory: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="page_*.png を含むディレクトリ",
    ),
) -> None:
    pngs = sorted(directory.glob("page_*.png"))
    if not pngs:
        typer.echo(f"[エラー] {directory} に page_*.png が見つかりません", err=True)
        raise typer.Exit(code=1)
    out_path = directory.parent / f"{directory.name}.pdf"
    build_pdf(pngs, out_path)
    typer.echo(f"PDF を作成しました: {out_path}")


def run_capture() -> None:
    typer.run(capture)


def run_rebuild_pdf() -> None:
    typer.run(rebuild_pdf)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: 全 6 テスト pass

- [ ] **Step 5: 全ユニットテストが揃って通ることを確認**

Run: `uv run pytest -v`
Expected: 全 44 テスト pass、`live` マークの 1 テストは skipped

- [ ] **Step 6: コミット**

```bash
git add src/kindle_cap/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): typer ベースの kindle-cap / kindle-cap-pdf を追加"
```

---

## Task 9: integration テスト — 実機 1 回の動作確認

**Files:**
- Create: `tests/integration/test_real_capture.py`

- [ ] **Step 1: integration テストを書く**

```python
# tests/integration/test_real_capture.py
"""手動 integration テスト。

実行方法:
  1. Kindle.app を起動し、任意の書籍を 1 ページ目で開く
  2. システム設定 > アクセシビリティ で iTerm2 等のターミナルを許可
  3. `uv run pytest -m live -v` を実行
"""
from pathlib import Path

import pytest

from kindle_cap.config import CaptureConfig, Direction
from kindle_cap.orchestrator import run


@pytest.mark.live
def test_capture_two_pages_real(tmp_path: Path) -> None:
    config = CaptureConfig(
        name="live-test",
        pages=2,
        direction=Direction.RTL,
        wait=1.5,
        out=tmp_path,
        keep_png=True,
    )
    run(config)
    out_dir = tmp_path / "live-test"
    assert (out_dir / "page_001.png").exists()
    assert (out_dir / "page_002.png").exists()
    assert (tmp_path / "live-test.pdf").exists()
    # PDF が空でないことだけ最低限確認
    assert (tmp_path / "live-test.pdf").stat().st_size > 1000
```

- [ ] **Step 2: 通常実行ではスキップされることを確認**

Run: `uv run pytest -v`
Expected: 全 44 ユニット pass、`test_capture_two_pages_real` は skipped

- [ ] **Step 3: 手動で実機テスト**

事前準備:
1. `Amazon Kindle.app` を起動して、好きな書籍を 1 ページ目で表示
2. システム設定 > プライバシーとセキュリティ > アクセシビリティ で、ターミナル（iTerm2 等）が許可されていることを確認

Run: `uv run pytest -m live -v`
Expected: `test_capture_two_pages_real PASSED`、Kindle が 2 ページ進んでいる

確認: `tmp_path` の場所は pytest の出力に表示される。中身の PNG と PDF が見えれば OK

- [ ] **Step 4: コミット**

```bash
git add tests/integration/test_real_capture.py
git commit -m "test(integration): 実機 2 ページ撮影の手動テストを追加"
```

---

## Task 10: 実機スモークテスト（5 ページ程度）

**Files:** （変更なし、実行のみ）

- [ ] **Step 1: 短い書籍で実機動作確認**

事前準備:
1. Kindle.app で書籍を 1 ページ目に開く
2. アクセシビリティ権限が iTerm2 等に付与されていることを確認

Run:
```bash
uv run kindle-cap --name smoke-test --pages 5 --direction rtl --wait 1.0
```

確認:
- `output/smoke-test/page_001.png`〜`page_005.png` の 5 枚が存在
- `output/smoke-test.pdf` が存在し、5 ページの PDF として開ける
- Kindle 上で書籍が 5 ページ目を表示している

- [ ] **Step 2: dry-run の動作確認**

```bash
uv run kindle-cap --name dry --pages 1 --direction rtl --dry-run
```

確認:
- `output/dry_run.png` が 1 枚作成されている
- stdout に `window geometry: x=0 y=31 w=... h=...` が表示される
- PDF は作られない

- [ ] **Step 3: 既存 PNG ディレクトリからの PDF 再生成**

```bash
uv run kindle-cap-pdf output/smoke-test
```

確認:
- `output/smoke-test.pdf` が再生成される
- stdout に `PDF を作成しました: output/smoke-test.pdf` が表示される

- [ ] **Step 4: 中断テスト（Ctrl-C）**

```bash
uv run kindle-cap --name interrupted --pages 100 --direction rtl --wait 1.5
```

実行中に `Ctrl-C` を押す。確認:
- 「中断しました。N/100 ページまで撮影済み」の表示
- `output/interrupted/page_001.png` 〜途中まで PNG が残る
- `output/interrupted.pdf` は作られない

- [ ] **Step 5: スモークの記録を残さない場合は output/ を削除**

```bash
rm -rf output/smoke-test output/dry output/interrupted output/smoke-test.pdf
```

（`.gitignore` で `output/` は除外済みなので git には影響なし）

---

## Acceptance Criteria

すべての項目を満たしたら実装完了:

- [ ] `uv run pytest` が 44 テスト pass、live 1 件 skipped
- [ ] `uv run pytest -m live` が実機で pass
- [ ] `uv run kindle-cap --name smoke-test --pages 5 --direction rtl` で 5 ページ撮れて PDF ができる
- [ ] `uv run kindle-cap --dry-run` で 1 枚だけ撮れて PDF は作られない
- [ ] `uv run kindle-cap-pdf <dir>` で既存 PNG から PDF を再生成できる
- [ ] Ctrl-C で中断したとき PNG が保持されて PDF は作られない
- [ ] `--direction ltr` を指定すると左矢印（key code 123）が送られる（試したい場合は適当な英書で確認）
