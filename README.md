# kindle-calibre

Kindle書籍をCalibreライブラリに一括インポート・管理するCLIツール。

## 機能

- **一括インポート**: Kindle for Mac / Kindle端末の全書籍をCalibreに取り込み
- **ワンコマンド追加**: 新規購入書籍をコマンド一発で追加
- **フォーマット変換**: EPUB / PDF への自動変換
- **重複防止**: 処理済みファイルの追跡で二重インポート回避

## セットアップ

```bash
# 前提条件
# - macOS
# - Calibre インストール済み
# - DeDRM (NoDRM) プラグイン設定済み

# インストール
pip install -e ".[dev]"

# 設定確認
kindle-calibre config show
```

## 使い方

```bash
# 一括インポート
kindle-calibre import --source both

# 新規書籍追加
kindle-calibre add

# ステータス確認
kindle-calibre status
```

## 開発

```bash
make install    # 開発環境セットアップ
make check      # lint + typecheck + test
make test-cov   # カバレッジ付きテスト
```

開発フローの詳細は [CLAUDE.md](CLAUDE.md) を参照。

## ライセンス

MIT
