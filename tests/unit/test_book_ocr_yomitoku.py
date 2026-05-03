"""YomiTokuEngine の subprocess 結果ハンドリング (純粋関数) のテスト."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from book_ocr.engines.yomitoku import (
    YomiTokuEngine,
    _ensure_yomitoku_succeeded,
)

# ---------------------------------------------------------------------------
# _ensure_yomitoku_succeeded (純粋関数)
# ---------------------------------------------------------------------------


class TestEnsureYomitokuSucceeded:
    def test_does_not_raise_on_zero_returncode(self) -> None:
        # 何も raise しないこと (戻り値 None)
        _ensure_yomitoku_succeeded(0, "ok", "")

    def test_does_not_raise_when_stderr_present_but_returncode_zero(self) -> None:
        """yomitoku は warning を stderr に書きつつ exit 0 を返すことがある.

        returncode=0 なら成功とみなす (stderr 内容に関わらず)。
        """
        _ensure_yomitoku_succeeded(0, "", "warning: deprecated")

    def test_raises_runtime_error_on_nonzero_returncode(self) -> None:
        with pytest.raises(RuntimeError):
            _ensure_yomitoku_succeeded(1, "out", "err")

    def test_error_message_contains_exit_code(self) -> None:
        with pytest.raises(RuntimeError, match="exit=1"):
            _ensure_yomitoku_succeeded(1, "", "")

    def test_error_message_contains_negative_exit_code(self) -> None:
        """SIGKILL (-9) など負の exit code もメッセージに出る."""
        with pytest.raises(RuntimeError, match="exit=-9"):
            _ensure_yomitoku_succeeded(-9, "", "killed by signal 9")

    def test_error_message_contains_stdout(self) -> None:
        with pytest.raises(RuntimeError, match="UNIQUE_STDOUT_TOKEN"):
            _ensure_yomitoku_succeeded(2, "UNIQUE_STDOUT_TOKEN", "")

    def test_error_message_contains_stderr(self) -> None:
        with pytest.raises(RuntimeError, match="UNIQUE_STDERR_TOKEN"):
            _ensure_yomitoku_succeeded(2, "", "UNIQUE_STDERR_TOKEN")


# ---------------------------------------------------------------------------
# YomiTokuEngine.timeout_sec デフォルト / カスタム
# ---------------------------------------------------------------------------


class TestYomiTokuEngineTimeoutSec:
    def test_default_timeout_is_1800_seconds(self) -> None:
        """デフォルト 30 分: 1 ページ ~8 秒 × 200 ページ + 余裕."""
        assert YomiTokuEngine().timeout_sec == 1800.0

    def test_custom_timeout_is_respected(self) -> None:
        engine = YomiTokuEngine(timeout_sec=60.0)
        assert engine.timeout_sec == 60.0


# ---------------------------------------------------------------------------
# subprocess.TimeoutExpired を RuntimeError に変換
# ---------------------------------------------------------------------------


class TestRunBatchTimeoutHandling:
    def test_timeout_expired_is_converted_to_runtime_error(self, tmp_path: Path) -> None:
        """yomitoku がハングしたら timeout で RuntimeError に変換される."""
        # 偽 yomitoku binary (実行可能)
        fake_bin = tmp_path / "yomitoku"
        fake_bin.write_text("#!/bin/sh\nexit 0\n")
        fake_bin.chmod(0o755)

        png = tmp_path / "page_001.png"
        png.write_bytes(b"")

        engine = YomiTokuEngine(yomitoku_bin=fake_bin, timeout_sec=0.001)

        timeout_error = subprocess.TimeoutExpired(cmd=["yomitoku"], timeout=0.001)
        with (
            patch("book_ocr.engines.yomitoku.subprocess.run", side_effect=timeout_error),
            pytest.raises(RuntimeError, match="timeout"),
        ):
            engine.run_batch([png])
