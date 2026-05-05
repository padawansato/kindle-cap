"""YomiTokuEngine — yomitoku CLI を subprocess で叩く batch 実装.

`chunk_size` を指定するとページを分割して **複数 subprocess** で順次処理する
(issue #36)。チャンク化により:

- 1 チャンクが timeout に収まる → 巨大本でも処理可能
- per-page 実行時間が batch size に比例して悪化する問題 (10p: 13s/p → 50p: 19s/p) を回避
- 各チャンク独立 tempdir で I/O 競合なし

`chunk_size=None` (default) は従来通り全 PNG を 1 subprocess に渡す挙動。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from book_ocr.models import PageText

_BINARY_NAME = "yomitoku"
_INPUT_DIR_NAME = "input"


@dataclass
class YomiTokuEngine:
    device: str = "mps"
    reading_order: str = "auto"
    ignore_meta: bool = True
    yomitoku_bin: Path | None = None  # 隔離 venv のバイナリを指す用
    # 1 ページ ~8 秒 × 200 ページ + 余裕で 30 分。巨大本では呼び出し側で延長
    timeout_sec: float = 1800.0
    # None なら全 PNG を 1 subprocess、int なら chunk_size 単位で分割実行 (issue #36)
    chunk_size: int | None = None

    def __post_init__(self) -> None:
        if self.chunk_size is not None and self.chunk_size < 1:
            raise ValueError(f"chunk_size must be >= 1 or None, got {self.chunk_size}")

    @property
    def name(self) -> str:
        return "yomitoku"

    def run_batch(self, pngs: list[Path]) -> list[PageText]:
        if not pngs:
            return []

        binary = self._resolve_binary()
        chunks = _split_into_chunks(pngs, self.chunk_size)

        all_pages: list[PageText] = []
        for chunk in chunks:
            all_pages.extend(self._run_one_subprocess(binary, chunk))
        return all_pages

    def _run_one_subprocess(self, binary: Path, pngs: list[Path]) -> list[PageText]:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            input_dir = tmp_dir / _INPUT_DIR_NAME
            output_dir = tmp_dir / "output"
            input_dir.mkdir()

            for png in pngs:
                (input_dir / png.name).symlink_to(png.resolve())

            cmd = [
                str(binary),
                str(input_dir),
                "-f",
                "md",
                "-o",
                str(output_dir),
                "-d",
                self.device,
                "--reading_order",
                self.reading_order,
            ]
            if self.ignore_meta:
                cmd.append("--ignore_meta")

            try:
                result = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                )
            except subprocess.TimeoutExpired as e:
                raise RuntimeError(
                    f"yomitoku timeout (exceeded {self.timeout_sec}s). "
                    f"巨大本では timeout_sec を延長するか、ページ数を分割してください。"
                ) from e

            _ensure_yomitoku_succeeded(result.returncode, result.stdout, result.stderr)

            return _collect_pages(pngs, output_dir, engine_name=self.name)

    def _resolve_binary(self) -> Path:
        if self.yomitoku_bin is not None:
            if not self.yomitoku_bin.exists():
                raise FileNotFoundError(
                    f"YomiTokuEngine.yomitoku_bin={self.yomitoku_bin} does not exist"
                )
            return self.yomitoku_bin
        path = shutil.which(_BINARY_NAME)
        if path is None:
            raise FileNotFoundError(
                f"{_BINARY_NAME} not found in PATH. Install with: uv pip install yomitoku"
            )
        return Path(path)


def _split_into_chunks(pngs: list[Path], chunk_size: int | None) -> list[list[Path]]:
    """`chunk_size` ごとに pngs を分割。`None` または `>= len(pngs)` なら 1 チャンクのまま。"""
    if chunk_size is None or chunk_size >= len(pngs):
        return [pngs]
    return [pngs[i : i + chunk_size] for i in range(0, len(pngs), chunk_size)]


def _ensure_yomitoku_succeeded(returncode: int, stdout: str, stderr: str) -> None:
    """yomitoku subprocess の戻り値を検査し、非ゼロ exit なら RuntimeError を raise.

    純粋関数として切り出しているので unit test で実 subprocess なしに網羅できる。
    """
    if returncode != 0:
        raise RuntimeError(
            f"yomitoku failed (exit={returncode}):\nstdout: {stdout}\nstderr: {stderr}"
        )


def _collect_pages(
    pngs: list[Path],
    output_dir: Path,
    engine_name: str,
) -> list[PageText]:
    """yomitoku が書き出した `<_INPUT_DIR_NAME>_<stem>_p1.md` ファイル群を PageText に変換する.

    yomitoku CLI でディレクトリを処理すると、出力ファイル名は
    `<input_dir_name>_<file_stem>_p1.md` というプレフィクス付きで生成される
    (例: 入力ディレクトリ "input" の page_001.png → "input_page_001_p1.md")。
    本関数は確定した命名規則で .md を読む。

    戻り値はページ番号の昇順。
    """
    by_number: dict[int, PageText] = {}
    for png in pngs:
        # page_001.png -> 1 (kindle-cap の出力規約に合わせる)
        try:
            n = int(png.stem.split("_")[-1])
        except ValueError as exc:  # pragma: no cover - 想定外フォーマット
            raise ValueError(
                f"Cannot derive page number from {png.name}; expected page_NNN.png"
            ) from exc

        md_path = output_dir / f"{_INPUT_DIR_NAME}_{png.stem}_p1.md"
        if not md_path.exists():
            raise FileNotFoundError(f"Expected yomitoku output {md_path} not found")

        markdown = md_path.read_text(encoding="utf-8")
        if n in by_number:
            raise ValueError(f"duplicate page number {n} in input pngs")
        by_number[n] = PageText(
            page_number=n,
            png_path=png,
            markdown=markdown,
            ocr_engine=engine_name,
        )

    return [by_number[n] for n in sorted(by_number.keys())]
