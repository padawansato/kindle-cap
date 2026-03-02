# AGENTS.md — Codex / AI Agent 向け開発指示書

## このリポジトリについて

Kindle → Calibre の書籍管理CLIツール。Python + Click + pytest。

## クイックスタート

```bash
make install   # 開発環境セットアップ
make check     # 全チェック（lint + type + test）
```

## 開発フロー（必ず守ること）

1. **仕様を読む**: `specs/` 内の該当specを必ず先に読む
2. **テストを書く**: `tests/` にテストを追加（失敗することを確認）
3. **実装する**: `src/kindle_calibre/` にコードを書く
4. **全チェック**: `make check` を通す
5. **コミット**: Conventional Commits形式

## ファイル構造の規約

| ディレクトリ | 役割 | 注意 |
|-------------|------|------|
| `specs/` | 仕様書（日本語） | 変更はオーナー承認が必要 |
| `tests/unit/` | ユニットテスト | 外部依存はすべてモック |
| `tests/integration/` | 統合テスト | `@pytest.mark.integration` |
| `tests/fixtures/` | テスト用ダミーデータ | |
| `src/kindle_calibre/core/` | ビジネスロジック | |
| `src/kindle_calibre/commands/` | CLIコマンド | |

## Calibre CLI のモック方法

```python
# テストでは CalibreClient をモックする
from unittest.mock import patch

@patch("kindle_calibre.core.calibre.CalibreClient.add_book")
def test_add(mock_add):
    mock_add.return_value = CalibreAddResult(book_id=42, success=True)
    ...
```

## やってはいけないこと

- specを読まずに実装を始めること
- テストなしでコードを追加すること
- `make check` が通らない状態でコミットすること
- `main` ブランチに直接pushすること
- Calibre CLIを実際に呼ぶユニットテストを書くこと
