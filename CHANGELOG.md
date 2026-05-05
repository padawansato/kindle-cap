# Changelog

このプロジェクトの変更履歴。形式は [Keep a Changelog](https://keepachangelog.com/) に準拠し、バージョニングは [Semantic Versioning](https://semver.org/) に従う。

## [Unreleased]

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
- `tqdm>=4.0` を `[ocr]` extra の依存に追加（yomitoku の transitive dep だが明示化）

### Changed

- **breaking**: `book_ocr.cli._run()` を削除。テスト/プログラム組み込みでエンジンを差し替えたい場合は新設の `book_ocr.cli.run_ocr_pipeline(book_dir, ..., engine=...)` を使う（issue #24）
- **breaking**: `book_ocr.protocols.OCREngine` から `@runtime_checkable` を削除。Protocol 適合は静的型 (`mypy`) で担保し、`isinstance(obj, OCREngine)` は使わない（issue #24）
- `book_ocr.engines.yomitoku._collect_pages` の `input_dir_name` 引数を削除し、モジュール定数 `_INPUT_DIR_NAME = "input"` に統一（issue #24）
- `book_ocr` パッケージに `py.typed` marker を追加。下流プロジェクトおよび当リポジトリの `tests/` で `book_ocr.*` の型情報が認識されるようになる（issue #11）

### Fixed

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

[Unreleased]: https://github.com/padawansato/kindle-cap/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/padawansato/kindle-cap/releases/tag/v0.1.0
