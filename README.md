# kindle-cap

[![CI](https://github.com/padawansato/kindle-cap/actions/workflows/ci.yml/badge.svg)](https://github.com/padawansato/kindle-cap/actions/workflows/ci.yml)

macOS の Amazon Kindle アプリで表示中の書籍を、ページ送りと撮影を自動化して 1 冊分の PDF にまとめる CLI ツール。

> [!CAUTION]
> **個人利用前提のツールです**。購入済みの書籍を別の閲覧環境（タブレットや OCR の入力）に流すために、画面を「目で読む代わりに自動でスクリーンショットする」だけのものです。**Kindle の DRM を回避する目的のものではなく、暗号化解除や複製の自動配布等は意図していません**。利用は購入者ご自身の責任で、書籍の利用規約に従ってください。

## 主な機能

- macOS の `screencapture` と `osascript` だけで動く（外部の DRM 解除ツール等は不要）
- 矢印キーを送って自動でページめくり
- ページ送り方向を `--direction rtl|ltr` で指定（rtl = 右綴じ / ltr = 左綴じ）
- `--auto-stop` で書籍末尾を自動検出して停止（リフロー型でページ数が読めない書籍に有効）
- `img2pdf` で PNG をストリーム出力で結合（1000 ページでもメモリ使用量は一定）
- 撮影中は `[i/N] capturing page` のリアルタイム進捗表示

## 必要環境（最低条件）

- macOS 14+
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Amazon Kindle.app（[Mac App Store 等から](https://www.amazon.co.jp/kindle-dbs/fd/kcp-mac)）
- 使用しているターミナルアプリにアクセシビリティ権限
  - `システム設定 > プライバシーとセキュリティ > アクセシビリティ` で当該アプリを許可
  - **権限は `osascript` を呼び出した親プロセスに付与される仕組み**のため、VS Code 統合ターミナル / iTerm2 / Terminal.app など、お使いのアプリ自体に許可が必要

## 動作確認済み環境（実機検証済み）

| 項目 | 値 |
|---|---|
| マシン | MacBook Air (Apple M1, 8 GB RAM) |
| OS | macOS 26.0.1 (Tahoe) |
| Kindle.app | 7.50 |
| ディスプレイ | 内蔵 Retina LCD（物理 2560x1600 / 論理 1440x900）単体使用 |

## 未検証の組み合わせ（理論上動くはずだが報告なし）

- Intel Mac、M2/M3 系 Apple Silicon
- macOS 14 / 15
- Kindle.app の他バージョン
- 外部ディスプレイ／マルチディスプレイ環境

### 環境依存の補足

実装上、コード自体は **マウス位置やディスプレイサイズに直接依存しません**。Kindle ウィンドウの絶対座標を毎ページ取り直し、`screencapture -R x,y,w,h` でその範囲を撮影するだけです。ただし以下は環境による:

- **撮影 PNG の解像度**: Retina なら 2x、non-Retina なら 1x（PDF の画質に影響）
- **キャプチャ速度**: マシン性能（M1 ≦ M3 Pro 等）
- **書籍方向**: Kindle for Mac 上の `direction` は紙の綴じ方向と一致しないケースあり（後述）

## インストール

```bash
git clone https://github.com/padawansato/kindle-cap.git
cd kindle-cap
uv sync
```

## 使い方

### 基本

```bash
# 1. Kindle.app で書籍を開き、表紙ページを表示する（Cmd+G で先頭ジャンプも可）
# 2. 撮影実行（direction を自動判定する場合）
uv run kindle-cap \
  --name my-book \
  --pages 600 \
  --auto-direction \
  --auto-stop \
  --wait 1.5

# 明示指定（rtl/ltr が分かっている場合）
uv run kindle-cap \
  --name my-book \
  --pages 600 \
  --direction rtl \
  --auto-stop \
  --wait 1.5
```

実行後の出力:

```text
output/my-book/
  page_001.png
  page_002.png
  ...
output/my-book.pdf
```

### オプション

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--pages N` | ✓ | — | 撮影ページ数の上限 |
| `--direction rtl\|ltr` | ※ | — | `rtl`=右綴じ（右矢印で次ページ）、`ltr`=左綴じ（左矢印で次ページ） |
| `--auto-direction` | ※ | off | 表紙起点で direction を試写判定。試写は本番に流用（重複撮影なし） |
| `--name NAME` | | （対話プロンプト） | 出力ディレクトリ名 |
| `--wait SEC` | | `1.0` | ページ送り後の待機秒（重い書籍は `1.5` 推奨） |
| `--out PATH` | | `./output` | 出力先 |
| `--keep-png / --no-keep-png` | | `--keep-png` | 中間 PNG を保持するか |
| `--dry-run` | | off | 1 枚だけ撮って位置確認用に保存（PDF は作らない） |
| `--auto-stop` | | off | 連続する 2 ページが同一なら書籍末尾と判断して停止 |
| `--pdf-jpeg-quality N` | | （未指定） | PDF 埋め込み画像を JPEG quality N (1-100) で再圧縮。未指定時は lossless PNG 埋め込み。**テキスト書籍は 80 程度推奨で PDF サイズが ~1/10 に** (issue #50) |

※ `--direction` または `--auto-direction` のいずれかが必須（同時指定はエラー）

> [!IMPORTANT]
> **direction についての注意**: Kindle for Mac 上の `direction` は紙の綴じ方向と必ずしも一致しない。リフロー型の和書（縦書き）でも左矢印で次ページ（`ltr`）になるケースがある。
> **推奨**: `--auto-direction` で表紙起点の試写による自動判定を使う（`--dry-run` で当てっこする手間が消える）。明示指定したい場合は従来通り `--direction rtl|ltr` も使える。

### 既存 PNG から PDF だけ再生成

```bash
uv run kindle-cap-pdf output/my-book
# → output/my-book.pdf を再生成

# JPEG 再圧縮で PDF サイズを縮小 (テキスト書籍向け)
uv run kindle-cap-pdf output/my-book --pdf-jpeg-quality 80
```

### book-ocr — OCR で Markdown / index.json を生成（オプション）

> [!TIP]
> **AI で読ませる用途は markdown を推奨**。本ツールの出力 PDF は典型的に 100 MB 〜 1 GB と大きく、Claude Code の `Read` ツールには **100 MB 上限 + `poppler` (`pdftoppm`) 依存** があるため直接渡せない。`book-ocr` で生成した markdown はサイズが PDF の約 1/500、token も 1/3-1/5 と効率的で、`Read` でそのまま開ける。PDF は視覚確認・人間閲覧用と割り切るのが実用的（実測レポート: [`docs/ai-readability/2026-05-20.md`](docs/ai-readability/2026-05-20.md)）。

撮影後に `book-ocr` を実行すると [YomiToku](https://github.com/kotaro-kinoshita/yomitoku) で OCR し、grep 可能な Markdown と index.json を生成する（既存 PNG / PDF はそのまま残る）。

```bash
# YomiToku を含めて再インストール（約 1.5GB の追加依存）
uv sync --extra ocr

# キャプチャ後に OCR を実行
uv run kindle-cap --name my-book --pages 200 --auto-direction
uv run book-ocr output/my-book/
```

実行後の出力:

```text
output/my-book/
  page_001.png ...                # 既存（キャプチャ時）
  index.json                      # 新規。{title, page_count, captured_at, ocr_engine, ocr_engine_version, ocr_settings, ocr_runtime, pages}
  my-book.md                      # 新規。全文連結（<!-- page:NNN --> 区切り）— grep 一発用
  pages/
    page_001.md ...               # 新規。ページ単位 Markdown
output/my-book.pdf                # 既存。視覚確認用
```

#### book-ocr のオプション

| オプション | デフォルト | 説明 |
|---|---|---|
| `--name TEXT` | book_dir の basename | 書籍名（Markdown ファイル名と index.json に反映） |
| `--device mps\|cpu\|cuda` | `mps` | OCR 推論デバイス（Apple Silicon は `mps` 推奨） |
| `--reading-order auto\|left2right\|top2bottom\|right2left` | `auto` | 読み順（自動検出推奨） |
| `--ignore-meta / --no-ignore-meta` | `--ignore-meta` | Kindle のヘッダー/フッターを除外 |
| `--out PATH` | `<book_dir>` | 出力先（省略時は book_dir に書き戻す） |
| `--chunk-size N` | None | ページを N 枚ずつ分割して OCR (issue #36)。巨大本で timeout 回避＆スケール改善 |
| `--timeout-sec N` | `1800.0` | yomitoku subprocess 1 回の timeout (秒、issue #37)。chunked 実行時は 1 chunk あたり |
| `--start-page N` | `1` | OCR 開始ページ番号 (1-indexed inclusive、issue #39) |
| `--end-page M` | None | OCR 終了ページ番号 (1-indexed inclusive、省略時は最後まで、issue #39) |
| `--progress / --no-progress` | `--progress` | chunked 実行時に tqdm で chunk 進捗を stderr に表示 (issue #38) |
| `--skip-existing` | off | 既存 `pages/page_NNN.md` があるページは OCR をスキップ (issue #41)。失敗後の再走を高速化 |

#### 性能の目安（Apple Silicon MPS）

- 1 ページあたり約 7〜9 秒（小規模、`--chunk-size` 不使用）
- バッチサイズが大きくなると per-page 時間が悪化（10p: 13s/p → 50p: 19s/p）。**100 ページ超は `--chunk-size 50` 推奨**
- 200 ページ本（chunked）: 約 65 分 / 500 ページ本（chunked）: 約 160 分
- 縦書き・横書きどちらも対応
- yomitoku の `subprocess.run(timeout=1800s)` で各 chunk が中断されるため、`--chunk-size 50` だと 1 chunk あたり ~16 分で安全マージン内

詳細な PoC レポートは [`docs/ocr-bench/2026-04-28.md`](docs/ocr-bench/2026-04-28.md) を参照。

### よくある使い方

```bash
# 短い書籍を 30 ページだけ
uv run kindle-cap --name short-book --pages 30 --direction rtl

# ページ数が読めない書籍を末尾自動検出
uv run kindle-cap --name my-book --pages 800 --direction ltr --auto-stop --wait 2.0

# 位置確認だけ（撮影しない）
uv run kindle-cap --pages 1 --direction rtl --dry-run
```

## 仕組み

```text
CLI (typer)
  ↓ CaptureConfig
Orchestrator
  ↓ preflight → for i in 1..N: activate → geometry → capture → arrow → wait
window.py / capture.py / keys.py / preflight.py
  ↓ subprocess
osascript / screencapture
```

- `osascript` で Kindle ウィンドウを前面化＋位置を取得
- `screencapture -R x,y,w,h -x` でウィンドウ範囲をキャプチャ
- 撮影直後に Pillow で RGB に flatten（`img2pdf` 警告と PDF 肥大化を回避）
- ページ送り後は `--wait` 秒だけ待機
- 全ページ撮り終わったら `img2pdf` でストリーム出力 PDF 結合

詳細は [`docs/superpowers/specs/2026-04-25-kindle-screenshot-design.md`](docs/superpowers/specs/2026-04-25-kindle-screenshot-design.md) を参照。

## 既知の制約

- **メニュー映り込み**: ウィンドウ全体を撮るため、Kindle のメニューバーが含まれる
- **モード崩れに注意**: 撮影中にユーザーが他アプリを最前面にすると矢印キーが他アプリに飛ぶ可能性（毎回 `activate` で緩和してるが完全ではない）
- **マルチディスプレイ対応**: 仮想スクリーン全体の座標系で動作する設計（純粋関数レベルでテスト済）。実機検証は単一ディスプレイで実施
- **アニメーションが重い書籍**: `--wait` を上げると安全
- **アクセシビリティ権限**: ターミナルに権限が必要。初回は OS の許可ダイアログを操作

## 開発

```bash
# 初回セットアップ
uv sync
uv run pre-commit install   # commit 前に ruff / mypy / 各種チェックを自動実行

# ユニットテスト
uv run pytest

# Kindle 起動済みでの実機テスト（live マーカー）
uv run pytest -m live

# 手動で全チェック
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pre-commit run --all-files   # 上記をまとめて実行
```

## ライセンス

[MIT](LICENSE) © 2026 padawansato
