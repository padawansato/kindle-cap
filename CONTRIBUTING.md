# Contributing

`kindle-cap` は個人利用前提の小さな CLI ですが、Issue や Pull Request は歓迎します。

## 開発環境のセットアップ

```bash
git clone https://github.com/padawansato/kindle-cap.git
cd kindle-cap
uv sync
uv run pre-commit install
```

`pre-commit` を install しておくと、commit 前に `ruff check`, `ruff format`, `mypy --strict`（`src/`）、その他の基本チェック（trailing whitespace, YAML/TOML 構文等）が自動実行されます。

## 開発ワークフロー

1. `main` から `feat/...`, `fix/...`, `chore/...`, `docs/...` のブランチを切る
2. **TDD 推奨**：先にテストを書いて失敗することを確認してから実装
3. `uv run pytest tests/unit/ -q` でユニットテスト全 pass を確認
4. 実機の挙動を変える場合は `uv run pytest -m live` で live integration を実行（Kindle 起動・アクセシビリティ権限が必要）
5. `uv run pre-commit run --all-files` で全フックが通ることを確認
6. push して Pull Request を作成

## コーディング規約

- **言語**：Python 3.12+
- **フォーマット**：`ruff format`（line-length=100）
- **リント**：`ruff check` の selected rules（E, F, I, UP, B, SIM, RUF）
- **型**：`mypy --strict`（`src/` のみ。テストは対象外）
- **テスト**：`pytest`、`@pytest.mark.live` で実機テストを分離

### TDD と mock の方針

このプロジェクトの設計判断:

- `subprocess.run` を mock しただけのテストでは「引数を組み立てられる」ことしか検証できない。実挙動のバグ（例：`screencapture` が RGBA で吐く）は E2E でしか発覚しない
- 対策：各モジュールから「純粋関数」（`_parse_geometry_output`, `_build_screencapture_args` 等）を切り出し、mock なしで境界値テスト
- システムコールに依存する部分は `@pytest.mark.live` で実コマンドを叩く integration を追加

## Pull Request の流れ

- タイトルは [Conventional Commits](https://www.conventionalcommits.org/) 準拠：`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:` 等
- PR 本文は GitHub テンプレートに従って Summary / Test plan を記入
- CI（`ruff check` / `ruff format --check` / `mypy` / `pytest`）が green であること
- レビュー後 `--merge --delete-branch` でマージ

## 設計判断・履歴

- 設計書：[`docs/superpowers/specs/2026-04-25-kindle-screenshot-design.md`](docs/superpowers/specs/2026-04-25-kindle-screenshot-design.md)
- 変更履歴：[`CHANGELOG.md`](CHANGELOG.md)

## 個人利用前提について

このツールは購入済み書籍を別環境に流すためのものです。Kindle DRM の回避や暗号化解除を目的とした PR は受け付けません。

## ライセンス

[MIT](LICENSE)
