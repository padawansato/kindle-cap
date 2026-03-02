# CLAUDE.md — Claude Code 向け開発指示書

このファイルは Claude Code がこのリポジトリで自律的に開発するための指示書です。

## プロジェクト概要

Kindle書籍をCalibreライブラリに一括インポート・管理するPython CLIツール。
macOS上で動作し、DeDRMプラグインと連携してKindle書籍のDRM解除・フォーマット変換を行う。

## アーキテクチャ

```
src/kindle_calibre/
├── cli.py              # Click CLIエントリポイント
├── core/
│   ├── scanner.py      # Kindleファイル検出
│   ├── calibre.py      # Calibre CLI (calibredb, ebook-convert) ラッパー
│   ├── converter.py    # フォーマット変換ロジック
│   ├── registry.py     # 処理済みファイル管理
│   └── config.py       # 設定管理
├── commands/
│   ├── bulk_import.py  # 一括インポートコマンド
│   ├── add_new.py      # 新規追加コマンド
│   └── status.py       # ステータス確認コマンド
```

## 開発ルール（厳守）

### 1. Spec駆動

- `specs/` ディレクトリ内の仕様書が真実の源泉（Single Source of Truth）
- 新機能はまず `specs/` に仕様を書いてからコードを書く
- 仕様と実装が矛盾する場合、仕様を優先する

### 2. テスト駆動 (TDD)

- **Red → Green → Refactor** のサイクルを厳守
- テストを先に書き、失敗を確認してから実装する
- テストは `tests/unit/` と `tests/integration/` に分離
- 外部依存（Calibre CLI、ファイルシステム）はモックする
- カバレッジ目標: 90%以上

### 3. 開発フロー

```
1. specs/ の仕様を読む
2. tests/ にテストを書く（Red）
3. src/ に実装を書く（Green）
4. リファクタリング（Refactor）
5. ruff check + mypy + pytest を全て通す
6. git commit（コミットメッセージは日本語OK、Conventional Commits形式）
```

### 4. コミットルール

- Conventional Commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`
- 1コミット = 1論理的変更
- テストが通らない状態でコミットしない

### 5. ブランチ戦略

- `main`: 安定版。直接pushしない
- `feat/*`: 機能開発ブランチ
- `fix/*`: バグ修正ブランチ
- PR経由でmainにマージ

## コマンド一覧

```bash
# テスト実行
make test              # 全テスト
make test-unit         # ユニットテストのみ
make test-integration  # 統合テストのみ
make test-cov          # カバレッジ付き

# 品質チェック
make lint              # ruff check + ruff format --check
make typecheck         # mypy
make check             # lint + typecheck + test （CI相当）

# 開発
make install           # 開発用インストール
make format            # コード自動フォーマット
```

## 外部依存の扱い

Calibre CLIコマンド (`calibredb`, `ebook-convert`) はsubprocessで呼び出す。
テスト時はすべてモックする。`tests/fixtures/` にダミーファイルとCLI出力のサンプルを置く。

## 設定ファイル

ユーザー設定は `~/.config/kindle-calibre/config.toml` に保存。
デフォルト値はすべて `src/kindle_calibre/core/config.py` で定義。

## 日本語について

- コミットメッセージ: 日本語OK
- コメント・docstring: 英語
- spec: 日本語
- CLI出力・ログ: 日本語
