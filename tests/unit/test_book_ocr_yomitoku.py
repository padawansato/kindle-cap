"""YomiTokuEngine の subprocess 結果ハンドリング (純粋関数) のテスト."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from book_ocr.engines.yomitoku import (
    YomiTokuEngine,
    _build_cmd,
    _build_render_manifest,
    _ensure_yomitoku_succeeded,
    _finalize_figure_refs,
    _parse_render_output,
    extract_figure_refs,
    rewrite_figure_refs,
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


# ---------------------------------------------------------------------------
# 図参照の抽出・書き換え (純粋関数)
# ---------------------------------------------------------------------------


class TestFigureRefs:
    def test_extract_figure_refs_returns_filenames_in_order(self) -> None:
        md = (
            '本文1\n\n<img src="figures/input_page_003_p1_figure_0.png" width="200px"><br>\n'
            '本文2\n\n<img src="figures/input_page_003_p1_figure_1.png" width="200px"><br>\n'
        )
        assert extract_figure_refs(md) == [
            "input_page_003_p1_figure_0.png",
            "input_page_003_p1_figure_1.png",
        ]

    def test_extract_figure_refs_empty_when_no_figures(self) -> None:
        assert extract_figure_refs("# 見出しのみ\n本文") == []

    def test_rewrite_figure_refs_renames_and_adds_alt(self) -> None:
        md = '前\n<img src="figures/input_page_003_p1_figure_0.png" width="200px"><br>\n後'
        rename = {"input_page_003_p1_figure_0.png": "page_003_figure_0.png"}
        result = rewrite_figure_refs(md, rename)
        assert '<img src="figures/page_003_figure_0.png" alt="図">' in result
        assert "width=" not in result
        assert "<br>" not in result
        assert "前" in result and "後" in result

    def test_rewrite_figure_refs_keeps_unknown_refs_untouched(self) -> None:
        md = '<img src="figures/unknown.png" width="200px"><br>'
        assert rewrite_figure_refs(md, {}) == md


# ---------------------------------------------------------------------------
# _build_cmd (純粋関数)
# ---------------------------------------------------------------------------


class TestBuildCmd:
    def test_requests_json_format(self) -> None:
        """OCR の正準形は JSON (issue #70)。md は別 worker が JSON から起こす。"""
        cmd = _build_cmd(
            binary=Path("/bin/yomitoku"),
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            device="mps",
            reading_order="auto",
            ignore_meta=True,
        )
        assert cmd[cmd.index("-f") + 1] == "json"

    def test_omits_figure_flags(self) -> None:
        """json exporter は --figure_letter を受け取らず、--figure は tmp に
        使わない画像を書くだけ。figures[] は常に JSON に含まれる。"""
        cmd = _build_cmd(
            binary=Path("/bin/yomitoku"),
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            device="mps",
            reading_order="auto",
            ignore_meta=True,
        )
        assert "--figure" not in cmd
        assert "--figure_letter" not in cmd

    def test_keeps_ignore_meta_and_reading_order(self) -> None:
        cmd = _build_cmd(
            binary=Path("/bin/yomitoku"),
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            device="mps",
            reading_order="top2bottom",
            ignore_meta=True,
        )
        assert "--ignore_meta" in cmd
        assert cmd[cmd.index("--reading_order") + 1] == "top2bottom"

    def test_omits_ignore_meta_when_disabled(self) -> None:
        cmd = _build_cmd(
            binary=Path("/bin/yomitoku"),
            input_dir=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            device="mps",
            reading_order="auto",
            ignore_meta=False,
        )
        assert "--ignore_meta" not in cmd


# ---------------------------------------------------------------------------
# md レンダ worker との受け渡し (純粋関数)
# ---------------------------------------------------------------------------


class TestRenderManifest:
    def test_manifest_carries_page_json_png_and_figure_target(self, tmp_path: Path) -> None:
        manifest = _build_render_manifest(
            entries=[(1, tmp_path / "page_001.png", tmp_path / "page_001.json")],
            figure_parent=tmp_path / "book",
            figure_dir_name="figures",
            export_figure=True,
        )
        assert manifest["export_figure"] is True
        assert manifest["figure_dir_name"] == "figures"
        (page,) = manifest["pages"]
        assert page["n"] == 1
        assert page["png"] == str(tmp_path / "page_001.png")
        assert page["json"] == str(tmp_path / "page_001.json")
        # figure_to_md は dirname(out_path)/figure_dir に書くので、out_path の
        # 親が figures/ の親、stem が figure 名の接頭辞になる
        assert page["out_path"] == str(tmp_path / "book" / "page_001.md")

    def test_export_figure_false_is_propagated(self, tmp_path: Path) -> None:
        manifest = _build_render_manifest(
            entries=[(3, tmp_path / "page_003.png", tmp_path / "page_003.json")],
            figure_parent=tmp_path,
            figure_dir_name="figures",
            export_figure=False,
        )
        assert manifest["export_figure"] is False


class TestParseRenderOutput:
    def test_maps_page_number_to_markdown(self) -> None:
        stdout = '{"pages": [{"n": 2, "markdown": "b"}, {"n": 1, "markdown": "a"}]}'
        assert _parse_render_output(stdout) == {1: "a", 2: "b"}

    def test_raises_on_non_json_stdout(self) -> None:
        with pytest.raises(RuntimeError, match="md レンダ worker"):
            _parse_render_output("Traceback (most recent call last):")

    def test_raises_when_pages_key_missing(self) -> None:
        with pytest.raises(RuntimeError, match="md レンダ worker"):
            _parse_render_output('{"unexpected": []}')


# ---------------------------------------------------------------------------
# figure 参照の最終形 (純粋関数)
# ---------------------------------------------------------------------------


class TestFinalizeFigureRefs:
    def test_strips_width_and_br_and_adds_alt(self, tmp_path: Path) -> None:
        """worker は最終ファイル名で figures を書くのでリネームは不要だが、
        width / <br> の除去と alt="図" の付与は golden 一致に必要 (Fable 指摘)。"""
        figures = tmp_path / "figures"
        figures.mkdir()
        (figures / "page_001_figure_0.png").write_bytes(b"x")
        md = '<img src="figures/page_001_figure_0.png" width="200px"><br>\n本文'
        assert (
            _finalize_figure_refs(md, figures)
            == '<img src="figures/page_001_figure_0.png" alt="図">\n本文'
        )

    def test_leaves_reference_untouched_when_file_missing(self, tmp_path: Path) -> None:
        figures = tmp_path / "figures"
        figures.mkdir()
        md = '<img src="figures/missing.png" width="200px"><br>'
        assert _finalize_figure_refs(md, figures) == md

    def test_no_figures_is_passthrough(self, tmp_path: Path) -> None:
        assert _finalize_figure_refs("本文のみ", tmp_path / "figures") == "本文のみ"


# ---------------------------------------------------------------------------
# YomiTokuEngine.settings に figure を含む
# ---------------------------------------------------------------------------


class TestEngineSettings:
    def test_settings_includes_figure(self) -> None:
        assert YomiTokuEngine(figure=False).settings["figure"] is False
        assert YomiTokuEngine().settings["figure"] is True
