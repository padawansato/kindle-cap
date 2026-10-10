"""yomitoku の JSON を markdown に起こす worker (yomitoku import を隔離する).

book_ocr 本体は yomitoku を **import しない**。理由は 2 つ:

- CI は `uv sync`（`--extra ocr` なし）で回るため、unit test から到達する
  モジュールが yomitoku を import すると即死する。`tests/unit/test_book_ocr_engine.py`
  の chunked 系テストは `subprocess.run` を mock して `run_batch` を実際に通すので、
  engine 内で in-process 変換すると必ず import 経路に乗ってしまう。
- `import yomitoku` は torch を含む全モジュールを引くので約 3 秒 / RSS 400MB かかる。

そこでこのファイルだけが yomitoku を import し、engine からは subprocess として
起動される。`YomiTokuEngine.yomitoku_bin` で隔離 venv を指す運用もそのまま保てる
（yomitoku バイナリと同じ venv の python で起動するため）。

呼び出し規約:

    <python> md_render_worker.py <manifest.json>

manifest:

    {"export_figure": bool,
     "figure_dir_name": "figures",
     "page_order": "auto" | "rtl" | "ltr" | "off",   # 省略時 off (issue #95)
     "pages": [{"n": int, "json": "...", "png": "...", "out_path": "..."}]}

stdout (成功時):

    {"pages": [{"n": int, "markdown": "..."}]}

`out_path` に md は書かない。`convert_markdown` は markdown 文字列を返すだけで、
`out_path` は figure の保存先 (`dirname(out_path)/<figure_dir_name>/`) と
figure ファイル名の接頭辞 (`<stem(out_path)>_figure_<i>.png`) を決めるためだけに
使われる (`yomitoku/export/export_markdown.py` の `figure_to_md`)。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def drop_script_dir_from_sys_path() -> None:
    """自分の居るディレクトリを `sys.path` から外す。

    このファイルをスクリプトとして起動すると `sys.path[0]` が
    `src/book_ocr/engines/` になる。そこには **engine 本体の `yomitoku.py`** が
    あるため、外さないと `import yomitoku` が本物のパッケージではなく engine
    モジュールを掴み、`No module named 'yomitoku.data'` で落ちる。

    ついでに空文字列 (カレントディレクトリ) も落とす。呼び出し元の cwd に
    `yomitoku.py` が置かれていても同じ事故が起きるため。
    """
    here = str(Path(__file__).resolve().parent)
    sys.path[:] = [p for p in sys.path if p and str(Path(p).resolve()) != here]


def ensure_book_ocr_importable() -> None:
    """`book_ocr.reading_order` を import できるよう `src/` を sys.path に足す。

    隔離 venv の python で起動される場合、その venv に book_ocr は入っていない。
    reading_order は純 Python で依存が無いので、このファイルの位置から src/ を
    逆算して足せば十分 (issue #95)。"""
    src = str(Path(__file__).resolve().parents[2])
    if src not in sys.path:
        sys.path.append(src)


def render(manifest: dict[str, Any]) -> dict[str, Any]:
    """manifest の各ページを markdown 化して返す (figure 画像は副作用で書かれる)."""
    drop_script_dir_from_sys_path()
    ensure_book_ocr_importable()

    # yomitoku の import はこの関数の中だけ。モジュール top-level に置くと
    # 本 worker を import しただけで torch が引かれる。
    from yomitoku.data.functions import load_image
    from yomitoku.export.export_markdown import convert_markdown
    from yomitoku.schemas import DocumentAnalyzerSchema

    from book_ocr.reading_order import fix_reading_order

    export_figure = manifest["export_figure"]
    figure_dir_name = manifest["figure_dir_name"]
    page_order = manifest.get("page_order", "off")

    rendered: list[dict[str, Any]] = []
    for page in manifest["pages"]:
        raw = json.loads(Path(page["json"]).read_text(encoding="utf-8"))
        # 見開きのページ順と縦書き 2 段組の連結 (issue #95)。JSON ファイルは変えない
        raw = fix_reading_order(raw, page_order=page_order)
        schema = DocumentAnalyzerSchema(**raw)

        # figure を切り出すときだけ画像が要る。yomitoku CLI と同じ load_image を
        # 使うことで、切り出される図が現行出力とバイト一致する。
        img = load_image(page["png"])[0] if export_figure else None

        markdown, _elements = convert_markdown(
            schema,
            page["out_path"],
            img=img,
            # CLI の --figure_letter 相当。既定は False なので明示しないと
            # 図中テキストが本文から静かに欠落する。
            export_figure_letter=True,
            export_figure=export_figure,
            figure_dir=figure_dir_name,
        )
        rendered.append({"n": page["n"], "markdown": markdown})

    return {"pages": rendered}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <manifest.json>", file=sys.stderr)
        return 2
    manifest = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    json.dump(render(manifest), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
