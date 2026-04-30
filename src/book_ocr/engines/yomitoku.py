"""YomiTokuEngine — yomitoku CLI を 1 回の subprocess で叩く batch 実装."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from book_ocr.models import PageText

_BINARY_NAME = "yomitoku"


@dataclass
class YomiTokuEngine:
    device: str = "mps"
    reading_order: str = "auto"
    ignore_meta: bool = True
    yomitoku_bin: Path | None = None  # 隔離 venv のバイナリを指す用

    @property
    def name(self) -> str:
        return "yomitoku"

    def run_batch(self, pngs: list[Path]) -> list[PageText]:
        if not pngs:
            return []

        binary = self._resolve_binary()

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            input_dir = tmp_dir / "input"
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

            subprocess.run(cmd, check=True, capture_output=True, text=True)

            return _collect_pages(pngs, output_dir, input_dir.name, engine_name=self.name)

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


def _collect_pages(
    pngs: list[Path],
    output_dir: Path,
    input_dir_name: str,
    engine_name: str,
) -> list[PageText]:
    """yomitoku が書き出した `<input_dir>_<stem>_p1.md` ファイル群を PageText に変換する.

    yomitoku CLI でディレクトリを処理すると、出力ファイル名は
    `<input_dir_name>_<file_stem>_p1.md` というプレフィクス付きで生成される
    (例: 入力ディレクトリ "input" の page_001.png → "input_page_001_p1.md")。
    本関数は input_dir_name を引数に取り、確定した命名規則で .md を読む。

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

        md_path = output_dir / f"{input_dir_name}_{png.stem}_p1.md"
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
