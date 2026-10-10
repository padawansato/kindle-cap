# Changelog

このプロジェクトの変更履歴。形式は [Keep a Changelog](https://keepachangelog.com/) に準拠し、バージョニングは [Semantic Versioning](https://semver.org/) に従う。

## [Unreleased]

## [0.9.0] - 2026-10-11

### Added

- `kindle-cap` / `kindle-cap-all --background`（既定）：撮影中に Kindle を前面に出さなくなった。`screencapture -R`（画面領域）の代わりに窓 ID 指定の `CGWindowListCreateImage`、`System Events key code`（前面アプリ宛て）の代わりに pid 宛ての `CGEventPostToPid` を使うので、Kindle の窓を他の窓の裏に置いたまま Mac で別の作業をしながら回せる。毎ページの `activate` とマウス退避も無くなった。窓を隠す（Cmd+H）・最小化する・別のデスクトップに移すと撮れないので、その間は失敗にせず警告を出して表示されるまで待つ。`kindle-cap-all` では本を開く・先頭に戻す・閉じる工程だけ従来どおり一瞬前面に出る（ライブラリの AXPress は前面でないと選択モードになるため）。従来の挙動は `--foreground`（issue #84）

## [0.8.0] - 2026-10-11

### Changed

- **breaking**: `kindle-cap` の `--pages`（必須）と `--auto-stop` を廃止し、`kindle-cap-all` と同じ `--max-pages`（既定 3000）に統一した。書籍末尾の自動検出（同一ページが 2 回続いたら停止）は常時 on になり、ページ数を事前に調べて指定する必要がなくなった。`--max-pages` は終端検出が効かなかったときの保険で、上限に達して止まった場合は「書籍末尾は未検出」と警告を出す（終端で止まったのか上限で切れたのかを後から区別できるようにするため。`--pages 1000` で撮った書籍が実は 1000 ページ超だった事例があった）。旧フラグを渡すとエラーになるので、シェル履歴や `&&` 連結スクリプトの `--pages N --auto-stop` を削除すること

## [0.7.0] - 2026-10-10

### Added

- `kindle-cap-all`：Kindle.app のライブラリにある書籍を一括でキャプチャする新コマンド。本を 1 冊ずつ手で開いて 1 ページ目を出す準備が不要になった。ライブラリ画面をアクセシビリティ API（PyObjC）で読み取って書籍を列挙し、順に「開く（未ダウンロードならダウンロード）→ 前ページキーで先頭まで戻す → `--auto-stop` 相当で全ページ撮影 → PDF → 閉じる」を回す。綴じ方向はリーダーのステータス文（`N ページ中の M ページ目`）と画面ハッシュから自動判定。既に `output/<書籍名>.pdf` がある本は飛ばすので再実行で続きから進む。`--list` で対象の確認、`--only` / `--limit` / `--include-pdf` で絞り込み。サンプル本（挙動が違う）とシリーズ（`巻`。漫画などで、方針として対象外）は飛ばす
- 依存に `pyobjc-framework-ApplicationServices` / `pyobjc-framework-Quartz`（macOS のみ）を追加

## [0.6.1] - 2026-10-10

### Changed

- `book-ocr --searchable-pdf`：テキスト層の描画を語ごとの `TextWriter` から「縦横の向きが同じ連続する語の run」ごとにまとめ、1000 ページの所要時間を 136 秒 → 68 秒、出力サイズの増分を 28MB → 7MB に減らした。抽出順・座標は変わらない（issue #70）

## [0.6.0] - 2026-10-10

### Added

- `book_ocr.exporters.searchable_pdf`：OCR の生 JSON（`pages/page_NNN.json`）から、kindle-cap が作った画像 PDF に不可視テキスト層を重ねてコピー・検索できる PDF を作る exporter を追加（issue #70）。yomitoku 標準の `create_searchable_pdf` は語の 15〜20% を落とし、縦書きを全角化（「6時半」→「６時半」）して 1 文字ずつ描くため使わず、全 `words[]` をそれぞれの矩形に語単位で描く。段落・図・表は読み順の決定にだけ使う。PDF を作り直さないので画像の再エンコードが無く、出力は元 PDF + 数十 KB。CLI からの呼び出しは次の PR
- 依存に `pymupdf` を追加（AGPL。個人利用 CLI のため許容）
- `book-ocr --searchable-pdf`：上記 exporter を CLI から使えるようにした。`output/<book>.pdf` に不可視テキスト層を重ねて `<out_dir>/<title>.searchable.pdf` を書く。`--skip-existing` と併用すれば既存 JSON から再 OCR なしで PDF だけ作り直せる。JSON の無いページ（v0.5.0 より前に OCR したページ）は無言で再 OCR せず、ページ番号を列挙して警告する。元 PDF が無ければ PNG から画像 PDF を組む。`--source-pdf PATH` で元 PDF を差し替え可能。`index.json` に `searchable_pdf` キーを additive に記録し、ディスク容量の事前チェックに元 PDF 分を上乗せする（issue #70）

- `kindle-cap --crop-top N`：撮影矩形の上端から N 論理ポイントを削る。System Events が返すウィンドウ frame はタイトルバー（信号機ボタン）を含むため、固定型書籍ではページ画像上端にボタンが写り込んでいた。既定値 0 で従来と同じ挙動。`--dry-run` / `--auto-direction` の試写にも同じ crop が適用される。`CaptureConfig.crop_top` と純粋関数 `kindle_cap.capture.crop_top(geom, points)` を追加（issue #69）

### Changed

- `kindle-cap`：orchestrator が投げる `ValueError`（`crop_top` がウィンドウ高さ以上など）を traceback ではなく `logger.error` + exit 1 で表示するようにした（issue #69）

## [0.5.0] - 2026-09-13

### Added

- `book-ocr`: OCR の生 JSON を `pages/page_NNN.json` に保存するようになった。`index.json` の `pages[]` にも `json` キーが additive に載る。文字単位の座標 (`words[].points`) と縦横の向きを含むので、ここから透明テキストレイヤーつき PDF を作れる（issue #70 の準備）。既存 JSON があれば再 OCR なしで後段の成果物を作り直せる

### Changed

- `book-ocr`: yomitoku の呼び出しを `-f md` から `-f json` に変更し、markdown は保存した JSON から生成するようにした。**出力される `pages/*.md` と `figures/*.png` は従来とバイト一致**（実書籍 11 ページで md 11/11・figure 21/21 を検証済み）なので、`book-epub` を含む下流への影響はない（issue #70）
- `book-ocr`: markdown 生成を `md_render_worker` として別プロセスに分離した。本体プロセスが yomitoku を import しなくなり、`yomitoku_bin` で隔離 venv を指す運用もそのまま保てる（issue #70）
- `book-ocr`: ディスク容量の事前チェックに JSON 出力分（100KB/ページ）を加算するようにした。JSON はチャンクをまたいで蓄積されるため、`--chunk-size` の指定に関わらず全ページ分を見積もる（issue #70）
- **breaking**: `ocr` extra の yomitoku 要件を `>=0.4` から `>=0.12,<1` に変更。markdown 生成が yomitoku の内部 API（`DocumentAnalyzerSchema` / `convert_markdown`）に直接依存するため。0.11 以前を使っている場合は `uv sync --extra ocr` で更新が必要（issue #70）

## [0.4.0] - 2026-07-29

### Added

- `book-epub`: 新コマンド。`book-ocr` の成果物（`pages/*.md` + `figures/`）から読み上げ可能な図表入り EPUB 3 を生成する

### Changed

- `book-ocr`: 図表切り出し（`--figure/--no-figure`、デフォルト有効）。図画像を `figures/` に保存し md に参照埋め込み（既存デフォルト挙動の変更）

## [0.3.0] - 2026-05-22

### Added

- `kindle-cap` / `kindle-cap-pdf` に `--verbose` (`-v`) / `--quiet` (`-q`) / `--log-file PATH` CLI オプション。それぞれ DEBUG レベル有効化 / WARNING 以上のみ出力 / ログをファイルにも記録（issue #62）
- `logging` モジュール導入（`kindle_cap` パッケージ全体）。フォーマット: `%(asctime)s %(levelname)-7s %(name)s: %(message)s`。`StreamHandler` (stderr) + optional `FileHandler` でレベル別に出力（issue #62）
- 新規 custom exception 3 種: `kindle_cap.window.WindowGeometryError` / `kindle_cap.window.KindleActivationError` / `kindle_cap.keys.KeystrokeError`。いずれも `RuntimeError` サブクラス。subprocess osascript の失敗時、`subprocess.CalledProcessError` を捕捉して stderr 込みの具体的メッセージで raise する（issue #62）

### Changed

- `kindle_cap.window.activate_kindle` / `kindle_cap.keys.send_next_page` で `capture_output=True` を有効化し、`subprocess.CalledProcessError` 発生時に stderr を例外メッセージ + `logger.error` に含めるようにした。従来は stderr が握り潰されており、`exit 1` しか Traceback に残らなかった（issue #62）
- `kindle_cap.window.get_window_geometry`: `subprocess.CalledProcessError` 発生時に `WindowGeometryError` (stderr 込み) で raise するように変更。`_parse_geometry_output` が投げていた `RuntimeError` も `WindowGeometryError` に統一（issue #62）
- `kindle_cap.preflight._run_oscript`: 失敗時に stderr を `logger.debug` に残してから例外を再送出（`_can_send_keystrokes` の stderr 判定経路は維持、issue #62）
- `kindle_cap.orchestrator._capture_book` のループ内で撮影 step が失敗したとき、`logger.exception` で `page N/M` + `captured so far: K` + `out_dir` を context として記録してから例外を再送出するように変更。2000 ページ撮影のような長時間ジョブで途中失敗したときの原因特定が容易になる（issue #62）
- `kindle-cap` / `kindle-cap-pdf` の進捗 / 完了メッセージを `print()` から `logger.info` 経由に移行。`--quiet` で抑制可能。エラー表示も `typer.echo("[エラー] ...", err=True)` から `logger.error` に統一（issue #62）

## [0.2.1] - 2026-05-22

### Fixed

- `--auto-direction` 経路で起点フレーム（表紙）が出力 PNG / PDF に含まれず欠落していた不具合を修正。`detect_direction()` が表紙を `_origin.png` として撮影したあと `finally` で削除し、probe direction で進めた後のフレームを `page_001.png..page_003.png` として保存していたのが原因。表紙を `page_001.png` として保持し、probe を `page_002.png..page_004.png` に変更。fallback 経路 (probe 無反応 → 逆方向 verify) でも `page_001.png` を表紙、`page_002.png` を verify として残す。「`page_001.png` のハッシュが起点フレームと一致する」という振る舞いベースのテストが欠落していたためレビューを素通りしていた点もテストで補強した (issue #59)

## [0.2.0] - 2026-05-20

### Added

- `--auto-direction`：表紙起点で試写し、ページ綴じ方向（rtl/ltr）を自動判定。試写 3 枚は本番に流用するため重複撮影しない（issue #15）
- 開発者向けドキュメント（`CHANGELOG.md`、`CONTRIBUTING.md`）
- GitHub の Issue / Pull Request テンプレート（`.github/`）
- `kindle_cap.pdf.PdfBuildError` 例外：`build_pdf` がディスク容量不足など予測可能な要因で失敗したことを表す
- `book_ocr.engines.yomitoku.YomiTokuEngine.timeout_sec`（デフォルト 1800 秒）：yomitoku がハングしたときに `RuntimeError` で抜けるための上限時間
- `book_ocr.cli.run_ocr_pipeline(book_dir, ..., engine=...)`：CLI から分離した OCR パイプライン公開関数。テストや組み込み利用で `engine` を注入できる
- `book_ocr.engines.yomitoku.YomiTokuEngine.chunk_size` および `book-ocr --chunk-size N` CLI オプション：ページを N 枚ずつ分割して **複数 subprocess で順次 OCR**。巨大本での timeout 回避と、batch size 増大に伴う per-page 時間悪化（10p: 13s/p → 50p: 19s/p の実測差）を回避する。`None`（デフォルト）は従来通り全 PNG を 1 subprocess に渡す（issue #36）
- `book-ocr --timeout-sec N` CLI オプション：yomitoku subprocess 1 回の timeout を秒単位で指定（デフォルト 1800.0）。chunked 実行時は 1 chunk あたりの上限。巨大本で延長が必要なケースに対応（issue #37）
- `index.json` に再現性・トラブルシュート用メタを additive に追加（issue #40）：
  - `ocr_engine_version`：実行時の yomitoku バージョン（`importlib.metadata` 由来、未取得時は `"unknown"`）
  - `ocr_settings`：`device`, `reading_order`, `ignore_meta`, `chunk_size`, `timeout_sec` の設定値
  - `ocr_runtime`：`started_at`, `finished_at`, `duration_sec`（`time.perf_counter()` 由来）
- `OCREngine` Protocol に `version: str` と `settings: dict[str, Any]` プロパティを追加（issue #40）
- `book-ocr --start-page N` / `--end-page M` CLI オプション：1-indexed inclusive で OCR 対象範囲を絞れる。失敗後の局所再走 (chunked 実行と組み合わせた retry や、巨大本の段階的処理) に有効（issue #39）
- `book-ocr --progress` / `--no-progress` CLI オプション + `YomiTokuEngine.progress`：chunked 実行時に `tqdm` で chunk 単位の進捗を stderr に表示。chunk 数 < 2 や非 tty 環境では自動的に無効化（issue #38）
- `tqdm>=4.0` を base 依存に追加（chunked 進捗表示で必要、CI でも常時入手するため `[ocr]` extra ではなく base に置く）
- `book-ocr --skip-existing` CLI オプション + `book_ocr.cli.run_ocr_pipeline(..., skip_existing=True)`：既存 `pages/page_NNN.md` があるページは OCR をスキップ。失敗後 chunk 単位 retry を高速化。空ファイルは missing 扱いで再 OCR される。既存 md 先頭の `<!-- page:NNN -->` プレフィクスは render_page_md と対称に剥がして PageText を再構成する（issue #41）
- `--pdf-jpeg-quality N` CLI オプション (`kindle-cap` / `kindle-cap-pdf` 双方) + `CaptureConfig.pdf_jpeg_quality` + `build_pdf(..., jpeg_quality=N)`：PDF 埋め込み画像を JPEG quality N (1-100) で再圧縮。未指定時は従来通り lossless PNG 埋め込み。テキスト書籍では quality 80 程度で同解像度のまま PDF サイズが ~1/10 になる (issue #50)
- `kindle-cap-pdf --progress` / `--no-progress` CLI オプション：JPEG 変換進捗を `tqdm` で stderr に表示。非 tty 環境では自動的に無効化（issue #53）
- `book-ocr` 起動時のディスク容量 preflight チェック：入力 PNG × 1.5 のマージンで `out_dir` / tempdir の残量を確認し、不足時は `PreflightError` で早期 exit。`--ignore-disk-check` でバイパス可能（issue #48）

### Changed

- **breaking**: `book_ocr.cli._run()` を削除。テスト/プログラム組み込みでエンジンを差し替えたい場合は新設の `book_ocr.cli.run_ocr_pipeline(book_dir, ..., engine=...)` を使う（issue #24）
- **breaking**: `book_ocr.protocols.OCREngine` から `@runtime_checkable` を削除。Protocol 適合は静的型 (`mypy`) で担保し、`isinstance(obj, OCREngine)` は使わない（issue #24）
- `book_ocr.engines.yomitoku._collect_pages` の `input_dir_name` 引数を削除し、モジュール定数 `_INPUT_DIR_NAME = "input"` に統一（issue #24）
- `book_ocr` パッケージに `py.typed` marker を追加。下流プロジェクトおよび当リポジトリの `tests/` で `book_ocr.*` の型情報が認識されるようになる（issue #11）

### Fixed

- `kindle-cap-pdf`: 1000 ページを超える書籍で PDF のページ順序が破綻していたのを修正。`sorted(directory.glob("page_*.png"))` が辞書順だったため、`page_1000.png` (4 桁) が `page_101.png` (3 桁) より前に挿入されていた。例: 1453 ページ書籍では PDF 最終ページが `page_999.png` で終わり、本来の最終 `page_1453.png` は中盤に紛れていた。`page_NNN` の数値で sort するように修正
- ディスク容量不足 (`ENOSPC`) で PDF 生成が失敗したときに生 traceback を露出していたのを改修。`PdfBuildError` を raise し、CLI で日本語の説明的メッセージ + exit 1 で終了する。部分書き込みされた PDF は削除し、PNG は保持して `kindle-cap-pdf` で再生成可能 (issue #19)
- `docs/ocr-bench/2026-04-28.md` の markdownlint 警告 5 件 (MD040 / MD032 / MD036) を解消 (issue #20)
- `book_ocr.engines.yomitoku.YomiTokuEngine`：yomitoku subprocess の stderr 握り潰しと timeout 未設定を改修。非ゼロ exit / timeout 双方で `stdout`/`stderr`/`exit code` を含む `RuntimeError` を raise (issue #21)
- `tests/integration/test_book_ocr_yomitoku.py` の yomitoku 不要なテスト 3 件を `tests/unit/test_book_ocr_engine.py` に移動して CI 実行対象に (issue #22)

## [0.1.0] - 2026-04-25

### Added

- 初リリース。macOS の Amazon Kindle で表示中の書籍をページ送り＋スクリーンショット自動化で 1 冊分の PDF にまとめる CLI ツール `kindle-cap`
- `--auto-stop`：連続する 2 ページが同一なら書籍末尾と判断して自動停止（リフロー型でページ数が読めない書籍に有効）
- `--dry-run`：1 枚だけ撮影して位置確認、PDF は作らない
- `--keep-png / --no-keep-png`：中間 PNG の保持を選択
- `kindle-cap-pdf <DIR>` 副コマンド：既存 PNG ディレクトリから PDF だけ再生成
- 進捗表示（`[i/N] capturing page`）
- `img2pdf` のストリーム出力で 1000+ ページでもメモリ消費が一定
- アクセシビリティ権限欠如やウィンドウ無しの preflight チェック
- マルチディスプレイ対応（仮想スクリーン座標系で動作、純粋関数レベルでテスト済）
- 開発基盤：`ruff`（lint + format）、`mypy --strict`（src/）、`pre-commit`、CI（macos-latest + Python 3.12 + uv）

### Notes

- 個人利用前提。Kindle DRM の回避目的ではなく、購入済み書籍を別環境（タブレット閲覧、後段の OCR）に流す入力素材生成のためのツール
- 設計ドキュメント：`docs/superpowers/specs/2026-04-25-kindle-screenshot-design.md`

[Unreleased]: https://github.com/padawansato/kindle-cap/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/padawansato/kindle-cap/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/padawansato/kindle-cap/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/padawansato/kindle-cap/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/padawansato/kindle-cap/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/padawansato/kindle-cap/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/padawansato/kindle-cap/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/padawansato/kindle-cap/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/padawansato/kindle-cap/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/padawansato/kindle-cap/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/padawansato/kindle-cap/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/padawansato/kindle-cap/releases/tag/v0.1.0
