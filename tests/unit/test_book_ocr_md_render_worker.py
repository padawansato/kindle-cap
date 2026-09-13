"""md レンダ worker のうち yomitoku を要さない部分のテスト.

worker 本体 (`render`) は yomitoku を import するので CI (`uv sync` に `--extra ocr`
なし) では回せない。ここでは import を伴わない純粋な前処理だけを検証する。
このモジュールを import しても yomitoku が引かれないこと自体も重要な性質。
"""

from __future__ import annotations

import sys
from pathlib import Path

from book_ocr.engines import md_render_worker


def test_importing_worker_does_not_import_yomitoku() -> None:
    """top-level で yomitoku を import していないこと (CI は extra ocr なしで回る)。"""
    assert "yomitoku" not in sys.modules


def test_drops_own_directory_from_sys_path() -> None:
    """engines/ には engine 本体の `yomitoku.py` があるので、外さないと
    `import yomitoku` が本物のパッケージを掴めない。"""
    here = str(Path(md_render_worker.__file__).resolve().parent)
    original = list(sys.path)
    try:
        sys.path[:] = [here, "/somewhere/else"]
        md_render_worker.drop_script_dir_from_sys_path()
        assert here not in sys.path
        assert "/somewhere/else" in sys.path
    finally:
        sys.path[:] = original


def test_drops_empty_string_cwd_entry() -> None:
    """cwd に yomitoku.py が置かれていても事故らないよう空文字列も落とす。"""
    original = list(sys.path)
    try:
        sys.path[:] = ["", "/somewhere/else"]
        md_render_worker.drop_script_dir_from_sys_path()
        assert "" not in sys.path
        assert "/somewhere/else" in sys.path
    finally:
        sys.path[:] = original


def test_keeps_unrelated_entries_intact() -> None:
    original = list(sys.path)
    try:
        sys.path[:] = ["/a", "/b", "/c"]
        md_render_worker.drop_script_dir_from_sys_path()
        assert sys.path == ["/a", "/b", "/c"]
    finally:
        sys.path[:] = original
