# Changelog

このプロジェクトの変更履歴。形式は [Keep a Changelog](https://keepachangelog.com/) に準拠し、バージョニングは [Semantic Versioning](https://semver.org/) に従う。

## [Unreleased]

### Added

- `--auto-direction`：表紙起点で試写し、ページ綴じ方向（rtl/ltr）を自動判定。試写 3 枚は本番に流用するため重複撮影しない（issue #15）
- 開発者向けドキュメント（`CHANGELOG.md`、`CONTRIBUTING.md`）
- GitHub の Issue / Pull Request テンプレート（`.github/`）

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
