# book-epub — 読み上げ可能な図表入り EPUB 生成 設計書

- 日付: 2026-07-29
- ステータス: 承認済み（ブレインストーミングセッションでユーザー承認）

## 目的

kindle-cap / book-ocr の成果物（ページ PNG + OCR Markdown）から、**Kindle の読み上げ機能で聴ける、図表も参照できるリフロー型 EPUB 3** を生成する。

## 背景と要求

- ユーザーは生成 EPUB を **Send to Kindle** で取り込み、Kindle アプリの読み上げ（Assistive Reader）で聴く。Send to Kindle の EPUB 受付上限は 200MB
- 図表は**ページ丸ごとではなく図表領域だけ切り出して**本文の流れに埋め込む（YomiToku の figure 抽出を利用）
- 読み上げ中に図表へ差し掛かったら、**図中のテキストも読み上げ対象**にする（`--figure_letter`）
- コマンドは **`book-epub` を新設**し、OCR（book-ocr）と EPUB 組立を分離。EPUB だけ何度でも作り直せる

### YomiToku CLI の根拠（公式確認済み）

`--figure` / `--figure_letter` / `--figure_width` / `--figure_dir` の存在は公式 README（https://github.com/kotaro-kinoshita/yomitoku ）およびローカルインストール版の `yomitoku --help` で確認済み。

- `--figure`: 検出した図・画像を出力ファイルにエクスポート
- `--figure_letter`: 図表内の文字も出力ファイルにエクスポート
- `--figure_dir`: 図画像の保存先ディレクトリ

## 実現方式の選定

| 案 | 内容 | 判定 |
|---|---|---|
| A | ebooklib（pure Python）で自前組立 | **採用** |
| B | pandoc | 外部バイナリ依存・細部の制御性が低く不採用 |
| C | calibre ebook-convert | 依存が最重量・md 直接入力不可で不採用 |

採用理由: uv 完結・純粋関数でテスト・外部ツール最小というプロジェクト方針に合致し、alt テキスト・ページマーカー・目次など「読み上げ最適化」の細部を完全制御できるため。

## データフロー全体

```text
kindle-cap        → output/my-book/page_NNN.png (+ my-book.pdf)
book-ocr (拡張)   → pages/page_NNN.md + figures/*.png + index.json + my-book.md
book-epub (新規)  → output/my-book/my-book.epub  → Send to Kindle
```

## book-ocr の拡張（figure 抽出）

- yomitoku コマンドに `--figure --figure_letter --figure_dir` を追加する。図表領域は同じレイアウト解析の副産物なので追加コストは小さい
- **デフォルト有効**、`--no-figure` でオプトアウト（既存挙動が変わるため minor バージョンアップ扱い）
- 切り出し画像は `<book_dir>/figures/` に保存
- yomitoku が md 内に書く図参照パスを、最終配置（`pages/page_NNN.md` から見た `../figures/xxx.png`）に合わせて書き換える
- `--figure_letter` により図中の文字が md 出力に含まれる。**alt 属性ではなく本文テキストとして残す**（Kindle 読み上げが確実に読むのは本文のため）。正確な出力形式は実装時に 1 ページ PoC で確認する
- `index.json` の `ocr_settings` に figure 設定を記録

### 既存資産への影響

既に OCR 済みの書籍で図表入り EPUB を作るには**再 OCR が必要**（figures/ が存在しないため）。`book-epub` は figures/ 不在でも「テキストのみ EPUB」として動作し警告を出す（再 OCR せずテキストだけ聴きたいケースの救済）。

## book-epub コマンド

```bash
uv run book-epub output/my-book/ [--title TEXT] [--author TEXT] [--out PATH]
```

- 入力: `pages/page_NNN.md` + `figures/` + `index.json`
- 出力: `<book_dir>/<name>.epub`（`--out` で変更可）
- タイトル優先順: `--title` > index.json の title > ディレクトリ名
- 言語は `ja` 固定（オプション化は YAGNI）

## EPUB 構造（EPUB 3・リフロー型・横書き）

- **1 ページ = 1 XHTML** で spine に並べる。ページ境界に `epub:type="pagebreak"` マーカーを埋め込む（読み上げでは読まれず、視覚閲覧時の位置対応が保たれる）
- **md → XHTML 変換**は `markdown` ライブラリ（pure Python）で行う。図参照は `<img src="../figures/x.png" alt="図"/>` に解決
- **目次（nav）**: md の見出し行（`#`〜`###`）から階層目次を生成。見出しが 1 つも無い書籍は書名 1 エントリのみ
- **表紙**: `page_001.png` があれば cover 画像に設定
- 縦書き対応は今回スコープ外（将来 issue として起票のみ）

## エラーハンドリング

| 状況 | 挙動 |
|---|---|
| `pages/` が無い | exit 1、「先に book-ocr を実行してください」と案内 |
| md が参照する図画像が無い | 警告して当該 img をスキップ、本文は維持 |
| `index.json` が無い | title をディレクトリ名にフォールバック（警告のみ） |
| `figures/` が無い | 警告を出しテキストのみ EPUB を生成 |

## テスト戦略（TDD・red-green-refactor）

- 純粋関数を unit test: md→XHTML 変換、図パス解決、見出し→目次抽出、ファイル名→ページ番号
- 統合テスト: 小さな fixture book_dir（3 ページ + 図 1 枚）→ EPUB 生成 → zipfile + ebooklib で開いて spine / nav / img / alt を検証
- mock は最小限（実ファイル I/O は tmp_path で実施）

## 新規依存

- `ebooklib`（EPUB 生成、pure Python）
- `markdown`（md → HTML 変換、pure Python）

いずれも base 依存に追加（OCR extra ではなく book-epub 単体で動くように）。
