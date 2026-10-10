"""YomiTokuEngine — yomitoku CLI を subprocess で叩く batch 実装.

`chunk_size` を指定するとページを分割して **複数 subprocess** で順次処理する
(issue #36)。チャンク化により:

- 1 チャンクが timeout に収まる → 巨大本でも処理可能
- per-page 実行時間が batch size に比例して悪化する問題 (10p: 13s/p → 50p: 19s/p) を回避
- 各チャンク独立 tempdir で I/O 競合なし

`chunk_size=None` (default) は従来通り全 PNG を 1 subprocess に渡す挙動。

`progress=True` (default) かつ chunk 数 >= 2 のとき、`tqdm` で chunk 単位の進捗を
stderr に表示する (issue #38)。
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tqdm import tqdm

from book_ocr.models import PageText
from book_ocr.reading_order import PAGE_ORDERS

_BINARY_NAME = "yomitoku"
_INPUT_DIR_NAME = "input"
# md レンダ worker のパス。yomitoku を import する唯一のファイルで、subprocess で起動する。
_WORKER_PATH = Path(__file__).with_name("md_render_worker.py")


def _resolve_worker_python(yomitoku_bin: Path) -> Path:
    """yomitoku バイナリと同じ環境の python を返す。

    `yomitoku_bin` で隔離 venv を指している場合でも、その venv の python で worker を
    起動すれば yomitoku を import できる。見つからなければ実行中の python に falls back。
    """
    candidate = yomitoku_bin.parent / "python"
    return candidate if candidate.exists() else Path(sys.executable)


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
    # chunked 実行時に tqdm で chunk 進捗を stderr に表示する (issue #38)
    progress: bool = True
    # issue #TBD(EPUB): 図表切り出し (--figure --figure_letter)。デフォルト有効
    figure: bool = True
    # 収集した図画像の最終保存先 (<book_dir>/figures)。None なら収集しない
    figure_out_dir: Path | None = None
    # OCR の生 JSON の保存先 (<book_dir>/pages)。None なら永続化しない (issue #70)
    json_out_dir: Path | None = None
    # issue #95: 見開きのページ順 (auto/rtl/ltr) と縦書き 2 段組の段落連結。off で無効
    page_order: str = "auto"

    def __post_init__(self) -> None:
        if self.chunk_size is not None and self.chunk_size < 1:
            raise ValueError(f"chunk_size must be >= 1 or None, got {self.chunk_size}")
        if self.page_order not in PAGE_ORDERS:
            raise ValueError(f"page_order must be one of {PAGE_ORDERS}, got {self.page_order!r}")

    @property
    def name(self) -> str:
        return "yomitoku"

    @property
    def version(self) -> str:
        """インストールされた yomitoku のバージョン (issue #40)。

        未インストール / 取得失敗時は `"unknown"` を返す。"""
        try:
            return importlib.metadata.version("yomitoku")
        except importlib.metadata.PackageNotFoundError:
            return "unknown"

    @property
    def settings(self) -> dict[str, Any]:
        """index.json に記録する OCR 設定 (issue #40)。"""
        return {
            "device": self.device,
            "reading_order": self.reading_order,
            "ignore_meta": self.ignore_meta,
            "chunk_size": self.chunk_size,
            "timeout_sec": self.timeout_sec,
            "figure": self.figure,
            "page_order": self.page_order,
        }

    def run_batch(self, pngs: list[Path]) -> list[PageText]:
        if not pngs:
            return []

        binary = self._resolve_binary()
        chunks = _split_into_chunks(pngs, self.chunk_size)

        all_pages: list[PageText] = []
        chunk_iter: Iterable[list[Path]] = _maybe_tqdm(chunks, enabled=self.progress)
        for chunk in chunk_iter:
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

            cmd = _build_cmd(
                binary,
                input_dir,
                output_dir,
                self.device,
                self.reading_order,
                self.ignore_meta,
            )

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

            entries = _collect_json_entries(pngs, output_dir)
            # tempdir は with を抜けると消えるので、JSON は engine 側でここで永続化する
            # (writer には運ばない。PageText.json_path が dangling になるのを防ぐ)。
            persisted = self._persist_json(entries)

            # figure の出力先。figure_out_dir が無いときは tempdir 配下に書かせる
            # (md 内の参照は残るが実体は残らない = 従来の挙動と同じ)。
            figures_dir = (
                self.figure_out_dir if self.figure_out_dir is not None else output_dir / "figures"
            )
            manifest = _build_render_manifest(
                entries,
                figure_parent=figures_dir.parent,
                figure_dir_name=figures_dir.name,
                export_figure=self.figure,
                page_order=self.page_order,
            )
            markdown_by_page = self._render_markdown(binary, manifest, tmp_dir)

            return [
                PageText(
                    page_number=n,
                    png_path=png,
                    markdown=_finalize_figure_refs(markdown_by_page[n], figures_dir),
                    ocr_engine=self.name,
                    json_path=persisted.get(n),
                )
                for n, png, _json_path in entries
            ]

    def _persist_json(self, entries: list[tuple[int, Path, Path]]) -> dict[int, Path]:
        """tmp の JSON を `<json_out_dir>/page_NNN.json` へ退避し、page -> 保存先を返す。"""
        if self.json_out_dir is None:
            return {}
        self.json_out_dir.mkdir(parents=True, exist_ok=True)
        saved: dict[int, Path] = {}
        for n, _png, json_path in entries:
            dest = self.json_out_dir / f"page_{n:03d}.json"
            shutil.copy(json_path, dest)
            saved[n] = dest
        return saved

    def _render_markdown(
        self, binary: Path, manifest: dict[str, Any], tmp_dir: Path
    ) -> dict[int, str]:
        """md レンダ worker を subprocess で起動して markdown を得る。

        本体プロセスに yomitoku を import させないための隔離
        (`md_render_worker` の docstring 参照)。
        """
        manifest_path = tmp_dir / "render_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        cmd = [str(_resolve_worker_python(binary)), str(_WORKER_PATH), str(manifest_path)]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"md レンダ worker timeout (exceeded {self.timeout_sec}s).") from e

        if result.returncode != 0:
            raise RuntimeError(
                f"md レンダ worker failed (exit={result.returncode}). "
                f"yomitoku が入っていない場合は `uv sync --extra ocr` を実行してください。\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return _parse_render_output(result.stdout)

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


def _maybe_tqdm(chunks: list[list[Path]], *, enabled: bool) -> Iterable[list[Path]]:
    """chunk 数 >= 2 かつ enabled かつ stderr が tty のとき、tqdm でラップする (issue #38)。

    1 chunk のときは進捗バーが意味を持たないため bare iterable を返す。
    CI など非 tty の場合は disable=True で tqdm を no-op にする。"""
    if len(chunks) < 2 or not enabled:
        return chunks
    wrapped: Iterable[list[Path]] = tqdm(
        chunks,
        desc="OCR (chunks)",
        unit="chunk",
        disable=not sys.stderr.isatty(),
    )
    return wrapped


def _build_cmd(
    binary: Path,
    input_dir: Path,
    output_dir: Path,
    device: str,
    reading_order: str,
    ignore_meta: bool,
) -> list[str]:
    """yomitoku CLI の引数リストを組み立てる純粋関数。

    出力形式は JSON 固定 (issue #70)。markdown は `md_render_worker` が同じ JSON から
    起こすので、OCR は 1 回で済む。

    figure 系フラグは付けない:
    - `--figure_letter` は json exporter が受け取らない (md/csv/html 専用)
    - `--figure` は tmp に使わない図画像を書くだけ。`figures[]` は指定の有無に
      関わらず JSON に含まれる
    図の切り出しは worker 側の `convert_markdown(export_figure=True)` が行う。
    """
    cmd = [
        str(binary),
        str(input_dir),
        "-f",
        "json",
        "-o",
        str(output_dir),
        "-d",
        device,
        "--reading_order",
        reading_order,
    ]
    if ignore_meta:
        cmd.append("--ignore_meta")
    return cmd


def _build_render_manifest(
    entries: list[tuple[int, Path, Path]],
    figure_parent: Path,
    figure_dir_name: str,
    export_figure: bool,
    page_order: str = "off",
) -> dict[str, Any]:
    """md レンダ worker に渡す manifest を組み立てる純粋関数。

    `out_path` は md の書き出し先ではなく、figure の保存先
    (`<figure_parent>/<figure_dir_name>/`) と figure 名の接頭辞
    (`page_NNN_figure_<i>.png`) を決めるためのもの。
    """
    return {
        "export_figure": export_figure,
        "figure_dir_name": figure_dir_name,
        "page_order": page_order,
        "pages": [
            {
                "n": n,
                "png": str(png),
                "json": str(json_path),
                "out_path": str(figure_parent / f"page_{n:03d}.md"),
            }
            for n, png, json_path in entries
        ],
    }


def _parse_render_output(stdout: str) -> dict[int, str]:
    """md レンダ worker の stdout をページ番号 -> markdown の dict にする純粋関数。"""
    try:
        payload = json.loads(stdout)
        pages = payload["pages"]
        return {int(p["n"]): str(p["markdown"]) for p in pages}
    except (ValueError, KeyError, TypeError) as e:
        raise RuntimeError(
            f"md レンダ worker の出力を解釈できませんでした: {e}\nstdout: {stdout[:2000]}"
        ) from e


def _finalize_figure_refs(markdown: str, figures_dir: Path) -> str:
    """worker が出した figure 参照を最終形に整える。

    worker は `figures/page_NNN_figure_i.png` という最終ファイル名で書くのでリネームは
    不要だが、`width="200px"` と `<br>` の除去、`alt="図"` の付与は現行出力との一致に
    必要 (`rewrite_figure_refs` が担当)。実ファイルが無い参照は書き換えず残す
    (book-epub 側が参照切れとして警告・スキップする)。
    """
    refs = extract_figure_refs(markdown)
    if not refs:
        return markdown
    rename = {name: name for name in refs if (figures_dir / name).exists()}
    return rewrite_figure_refs(markdown, rename)


def _ensure_yomitoku_succeeded(returncode: int, stdout: str, stderr: str) -> None:
    """yomitoku subprocess の戻り値を検査し、非ゼロ exit なら RuntimeError を raise.

    純粋関数として切り出しているので unit test で実 subprocess なしに網羅できる。
    """
    if returncode != 0:
        raise RuntimeError(
            f"yomitoku failed (exit={returncode}):\nstdout: {stdout}\nstderr: {stderr}"
        )


def _collect_json_entries(
    pngs: list[Path],
    output_dir: Path,
) -> list[tuple[int, Path, Path]]:
    """yomitoku が書き出した `<_INPUT_DIR_NAME>_<stem>_p1.json` を (n, png, json) に対応づける.

    yomitoku CLI でディレクトリを処理すると、出力ファイル名は
    `<input_dir_name>_<file_stem>_p1.<format>` というプレフィクス付きで生成される
    (例: 入力ディレクトリ "input" の page_001.png → "input_page_001_p1.json")。
    命名規約は md 出力時と同一 (`yomitoku/cli/main.py` の out_path 組み立て)。

    戻り値はページ番号の昇順。
    """
    by_number: dict[int, tuple[int, Path, Path]] = {}
    for png in pngs:
        # page_001.png -> 1 (kindle-cap の出力規約に合わせる)
        try:
            n = int(png.stem.split("_")[-1])
        except ValueError as exc:  # pragma: no cover - 想定外フォーマット
            raise ValueError(
                f"Cannot derive page number from {png.name}; expected page_NNN.png"
            ) from exc

        json_path = output_dir / f"{_INPUT_DIR_NAME}_{png.stem}_p1.json"
        if not json_path.exists():
            raise FileNotFoundError(f"Expected yomitoku output {json_path} not found")

        if n in by_number:
            raise ValueError(f"duplicate page number {n} in input pngs")
        by_number[n] = (n, png, json_path)

    return [by_number[n] for n in sorted(by_number.keys())]


# yomitoku md 出力の図参照: <img src="figures/<name>" width="NNNpx"><br>
_FIGURE_IMG_RE = re.compile(r'<img src="figures/([^"]+)"[^>]*>(?:<br>)?')


def extract_figure_refs(markdown: str) -> list[str]:
    """md 内の図参照ファイル名（figures/ 配下の basename）を出現順に返す。"""
    return _FIGURE_IMG_RE.findall(markdown)


def rewrite_figure_refs(markdown: str, rename: dict[str, str]) -> str:
    """図参照を最終ファイル名に書き換え、alt="図" を付与し width / <br> を除去する。

    `rename` に無い参照は元のまま残す（呼び出し側が警告を出す想定）。
    """

    def _sub(m: re.Match[str]) -> str:
        old = m.group(1)
        if old not in rename:
            return m.group(0)
        return f'<img src="figures/{rename[old]}" alt="図">'

    return _FIGURE_IMG_RE.sub(_sub, markdown)
