# Spec 05: CLI インターフェース

## 概要

Click ベースのCLIでユーザーと対話する。

## モジュール

`kindle_calibre.cli`

## コマンド体系

```
kindle-calibre
├── import       一括インポート
├── add          新規書籍追加
├── status       処理状況表示
├── config       設定確認・変更
└── reset        処理済みログリセット
```

### kindle-calibre import

既存のKindle書籍を一括インポート。

```
kindle-calibre import [OPTIONS]

Options:
  --source [mac|device|both]  取り込み元 (default: mac)
  --formats TEXT              出力フォーマット (default: epub,pdf)
  --dry-run                   処理対象の確認のみ
  --yes                       確認プロンプトをスキップ
```

出力例:
```
📚 Kindle書籍スキャン中...
  Kindle for Mac: 85冊検出（うち新規: 85冊）

📥 インポート開始 (85冊)
  [████████████████████████████████████████] 85/85

✅ 完了
  成功: 82冊
  スキップ: 0冊
  失敗: 3冊
  所要時間: 23分15秒
```

### kindle-calibre add

新規購入書籍を追加。

```
kindle-calibre add [OPTIONS] [FILE]

Options:
  --source [mac|device|both]  取り込み元 (default: mac)
  --formats TEXT              出力フォーマット (default: epub,pdf)

Arguments:
  FILE  直接ファイル指定（省略時はソースから自動検出）
```

### kindle-calibre status

処理状況を表示。

```
kindle-calibre status

出力例:
📊 処理状況
  処理済み: 152冊
  最終処理: 2026-03-02 10:30
  フォーマット: EPUB 152冊 / PDF 152冊

📁 ソース
  Kindle for Mac: 155冊検出（未処理: 3冊）
  Kindle端末: 未接続
```

### kindle-calibre config

```
kindle-calibre config show          設定一覧表示
kindle-calibre config set KEY VAL   設定変更
```

### kindle-calibre reset

```
kindle-calibre reset [--yes]        処理済みログリセット
```

## 共通オプション

```
--verbose / -v    詳細ログ
--quiet / -q      最小出力
--config PATH     設定ファイルパス指定
```

## 出力

- Rich ライブラリで進捗バー・色付き出力
- `--quiet` 時はプレーンテキスト（パイプ対応）
