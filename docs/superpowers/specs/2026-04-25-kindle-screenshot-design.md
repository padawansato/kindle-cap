# Kindleスクリーンショット → PDF化ツール設計

- 作成日: 2026-04-25
- 状態: ドラフト（ユーザーレビュー待ち）
- 対象 OS: macOS 14+（実験は 26.0.1 で確認済み）
- 利用形態: 個人利用 CLI（uv 管理の Python パッケージ）

## 1. 目的

macOS 上で起動した Amazon Kindle アプリの表示中ページを、ページ送りと撮影を自動化して画像群と単一 PDF に保存する。個人で購入済みの書籍を別の閲覧環境（タブレット、後段の OCR）に流すための入力素材を作る。

リポジトリは元々 Calibre 連携を意図した Python ツールの初期構造があったが、コミット `b2c2251` 以降のソースは作業ツリーで削除済み（更地）。今回はその更地に Kindle キャプチャ機能だけを切り出した独立ツールを組む。

## 2. 要件

### 2.1 機能要件

- F1. ユーザー指定のページ数だけ Kindle ウィンドウを連続キャプチャする
- F2. ページ送りは macOS の System Events 経由で矢印キーを送って実現する
- F3. 書籍の綴じ方向 (rtl=右綴じ、ltr=左綴じ) を CLI で必須指定し、対応する矢印キーを使い分ける
- F4. 撮影した PNG 群を 1 つの PDF にまとめる（再エンコードなし、`img2pdf` 使用）
- F5. 中間 PNG はデフォルトで保持。`--no-keep-png` で削除可能
- F6. `--dry-run` で 1 枚だけ撮影し、ウィンドウ位置とキャプチャ範囲の確認に使う
- F7. `--name`（書籍名・出力ディレクトリ名）が未指定なら対話プロンプトで聞く
- F8. `Ctrl-C` で中断したとき、撮影済み PNG は保持。PDF は作らない

### 2.2 非機能要件

- N1. macOS 14+ で動作（実験は 26.0.1）
- N2. 依存は最小：`typer`、`img2pdf`、`pytest` のみ。ImageMagick 等の外部ツール非要求
- N3. 1 ページの「撮影 → 次ページ送り」は概ね 2.0 秒前後（待機 1.0s + キャプチャ）
- N4. キャプチャは Retina 解像度（画面論理サイズ × 2）のまま保存。PDF も等倍

### 2.3 非ゴール（YAGNI）

- 中断後の再開機能
- OCR
- Calibre ライブラリ自動投入
- Windows / Linux 対応
- 自動トリミング（メニュー除去）

## 3. アーキテクチャ

```
┌── CLI (typer) ─────────────────────────────────┐
│ uv run kindle-cap --pages N --direction rtl   │
└──┬─────────────────────────────────────────────┘
   ▼
┌── Orchestrator ────────────────────────────────┐
│  preflight()                                  │
│  for i in 1..N:                               │
│    activate_kindle()                          │
│    geom = get_window_geometry()               │
│    capture_rect(geom, page_NNN.png)           │
│    if i < N: send_next_page(direction)        │
│    sleep(wait)                                │
│  build_pdf(pngs, <name>.pdf)                  │
└──┬─────────────────────────────────────────────┘
   ▼ subprocess ラッパー
┌── 各モジュール ────────────────────────────────┐
│ window.py / capture.py / keys.py /            │
│ preflight.py / pdf.py                         │
└────────────────────────────────────────────────┘
```

責務分離:

- `cli.py` は引数解析と対話プロンプトのみ。ロジックを持たない
- `orchestrator.py` はループ順序の制御だけ。subprocess を直接知らない
- `window.py` / `capture.py` / `keys.py` / `preflight.py` は 1 つのシステムコマンド呼び出しを 1 責務として持つ薄いラッパー
- `pdf.py` は純粋関数（パス入力 → パス出力）
- `config.py` は dataclass + バリデーション

この分離により、orchestrator のテストは各モジュール関数を mock するだけで完結する。

## 4. モジュール構成

```
src/kindle_cap/
  __init__.py
  cli.py            # typer の入口
  orchestrator.py   # 撮影ループ
  window.py         # get_window_geometry(), activate_kindle()
  capture.py        # capture_rect(geom, out_path)
  keys.py           # send_next_page(direction)
  pdf.py            # build_pdf(png_paths, out_path)
  preflight.py      # check_kindle_running(), check_accessibility()
  config.py         # CaptureConfig, Direction(StrEnum), Geometry
tests/
  unit/
    test_config.py
    test_pdf.py
    test_window.py        # subprocess.run を mock
    test_capture.py       # 同
    test_keys.py          # 同
    test_preflight.py     # 同
    test_orchestrator.py  # 各モジュールを mock
    test_cli.py           # typer.testing.CliRunner
  integration/
    test_real_capture.py  # @pytest.mark.live、Kindle 起動時のみ手動実行
  fixtures/
    sample_pages/         # PDF テスト用 PNG 3 枚
```

## 5. CLI 仕様

```
uv run kindle-cap [OPTIONS]

  --name TEXT                 書籍名（出力ディレクトリ名）。未指定時はプロンプトで聞く
  --pages INTEGER             撮影ページ数 [必須]
  --direction [rtl|ltr]       ページ送り方向 [必須]
                              rtl = 右綴じ（漫画・縦書き和書）→ 右矢印で次ページ
                              ltr = 左綴じ（小説・洋書）→ 左矢印で次ページ
  --wait FLOAT                ページ送り後の待機秒 [デフォルト: 1.0]
  --out PATH                  出力先ディレクトリ [デフォルト: ./output]
  --keep-png / --no-keep-png  中間 PNG を保持 [デフォルト: --keep-png]
  --dry-run                   1 枚だけ撮影し PDF は作らない（位置確認用）
  --auto-stop                 連続する 2 ページが同一なら書籍末尾と判断して停止
  --help                      ヘルプ
```

副コマンド:

```
uv run kindle-cap-pdf DIR     # 既存 PNG ディレクトリから PDF だけ再生成
                              # 出力先は DIR の親ディレクトリに <DIR名>.pdf
                              # 例: kindle-cap-pdf output/obsidian-ai
                              #     → output/obsidian-ai.pdf を生成
```

実行例:

```sh
uv run kindle-cap --name obsidian-ai --pages 30 --direction rtl
```

実行後の出力:

```
output/obsidian-ai/
  page_001.png
  page_002.png
  ...
  page_030.png
output/obsidian-ai.pdf
```

## 6. 動作仕様

### 6.1 起動時 preflight

1. `Kindle` プロセスを `osascript` で確認。なければ「Kindle.app を起動してください」と出して終了
2. ウィンドウが 1 枚以上あるか確認
3. アクセシビリティ権限の確認: 無害な System Events 呼び出しを試行し、`(-1719)` 等の権限エラーが出たら「システム設定 > プライバシーとセキュリティ > アクセシビリティ」で iTerm2（または親ターミナル）を許可するよう案内して終了
4. `--name` 未指定なら `typer.prompt("書籍名 (出力ディレクトリ名)")`

### 6.2 撮影ループ

```
out_dir = out_root / name
out_dir.mkdir(parents=True, exist_ok=True)

for i in range(1, pages + 1):
    activate_kindle()
    geom = get_window_geometry()        # 毎回再取得（ユーザーがウィンドウを動かしても追従）
    capture_rect(geom, out_dir / f"page_{i:03d}.png")
    if i < pages:                       # 最終ページの後は送らない（次の本へ行くリスク）
        send_next_page(direction)
        sleep(wait)
```

### 6.3 既存ファイル・ディレクトリの扱い

- `out_root / name` ディレクトリが既存でも作成エラーにしない
- 撮影開始前に `out_dir / "page_*.png"` を削除する（前回の残存 PNG が PDF に混入することを避ける）
- `out_root / <name>.pdf` が既存なら上書きする

### 6.4 終了処理

- 全ページ撮影成功時: `pdf.build_pdf(sorted(out_dir.glob("page_*.png")), out_root / f"{name}.pdf")`
- `--no-keep-png` の場合は PDF 生成後に PNG 群を削除
- `Ctrl-C` 受信時: ループを抜け、撮影済み PNG を保持し、PDF は生成せず、撮れたページ数を表示して終了

### 6.5 --dry-run

1. preflight 通過後、1 枚だけ `dry_run.png` として撮影
2. ウィンドウ位置とサイズを stdout に表示
3. PDF は作らない、PNG は `out_root / dry_run.png`

### 6.6 --auto-stop（書籍末尾の自動検出）

1. 各ページ撮影後、PNG ファイルの md5 ハッシュを計算
2. 直前のページのハッシュと一致したら「右矢印を送ってもページが変わらない＝書籍末尾」と判断
3. 重複した PNG ファイルを削除し、ループを break
4. PDF はそれまでの captured ページから生成

これにより、リフロー型でフォントを大きくしてページ数が増えた書籍など、
事前にページ数が読めない場合でも `--pages 600 --auto-stop` のように
余裕を持って指定すれば、自動的に末尾で停止できる。

## 7. データモデル

```python
class Direction(StrEnum):
    RTL = "rtl"
    LTR = "ltr"

@dataclass(frozen=True)
class Geometry:
    x: int
    y: int
    width: int
    height: int

@dataclass(frozen=True)
class CaptureConfig:
    name: str
    pages: int
    direction: Direction
    wait: float
    out: Path
    keep_png: bool

    def __post_init__(self) -> None:
        if self.pages <= 0:
            raise ValueError("pages must be positive")
        if self.wait < 0:
            raise ValueError("wait must be non-negative")
        if not self.name or "/" in self.name:
            raise ValueError("name must be non-empty and not contain '/'")
```

## 8. エラー処理

- subprocess 呼び出しは `check=True` で例外化。orchestrator がキャッチして「ページ N で失敗」とログを出す
- 1 ページの失敗で全体停止（中途半端な PDF を作らない）。撮影済み PNG は保持
- アクセシビリティ権限欠如は preflight で検出し、撮影開始前に止める
- ディスク容量不足は OS 例外をそのまま伝播

## 9. テスト方針（TDD）

実装は spec → test → impl の順で各モジュール：

1. `config.py`：dataclass バリデーションを `pytest.raises` で検証
2. `pdf.py`：fixture PNG 3 枚 → PDF。ページ数・寸法を検証
3. `window.py` / `capture.py` / `keys.py` / `preflight.py`：`subprocess.run` を `unittest.mock.patch` で mock し、引数文字列を検証
4. `keys.py` は direction 別（rtl→key code 124、ltr→key code 123）の送信を検証
5. `orchestrator.py`：各モジュールを mock し、3 ページ指定で `capture×3, send_next_page×2` を検証
6. `cli.py`：`typer.testing.CliRunner` で引数解析と対話プロンプトを検証
7. integration：`@pytest.mark.live` の手動テスト 1 本（Kindle 起動済みで実行）

CI ではユニットのみ。integration はローカル手動。

## 10. 既知の制約

- L1. キャプチャ範囲はウィンドウ全体。Kindle のメニューが映り込む可能性。トリミングは v1 では行わない
- L2. ページ送り中にユーザーが他アプリを最前面化すると矢印キーが他アプリに飛ぶ可能性。`activate_kindle()` を毎回呼ぶことで緩和するが完全ではない
- L3. アニメーションが重い書籍では 1.0 秒の wait で前ページが映る可能性。`--wait` で調整
- L4. Kindle が更新で UI を変えた場合、ウィンドウ取得が壊れる可能性
- L5. マルチディスプレイ環境では Kindle が外部ディスプレイ上にある場合も、仮想スクリーン全体の座標系で動作する設計（`osascript` の `position of window` も `screencapture -R` も負値・大値の座標を扱える）。純粋関数レベルでは負値・大値・マルチディスプレイ座標パターンをテストで網羅。ただし実機での外部ディスプレイ検証は未実施 — 想定外の挙動があればフィードバック推奨
- L6. Retina/non-Retina 混在ディスプレイ間で Kindle を移動した場合、撮影 PNG の物理ピクセル数が変わる（同じ論理サイズでも 1x と 2x で異なる）。PDF 内でページサイズが混在することになるが、`img2pdf` は各ページを独立したサイズで配置するので結合自体は問題ない

## 11. 将来の拡張余地（v1 では実装しない）

- `--resume`：中断後の続きから撮影
- `--ocr`：tesseract で OCR
- Calibre ライブラリ自動投入
- 自動トリミング（実コンテンツ領域の検出）
- 見開き分割（左右ページの分離）
- ライブラリ画面からの一括キャプチャ（PR #4 で `--from-library` として試行 → 実機検証で Kindle for Mac の制約により断念。再挑戦するなら GUI オートメーション前提の別アプローチが必要）
- `--auto-direction`：最初の数ページで矢印キーを試して進む方を採用（Kindle for Mac の direction が紙の綴じ方向と一致しないケースがあるため）

## 12. 実装順序の推奨

1. `pyproject.toml`（uv プロジェクト初期化、依存定義）
2. `config.py`（純粋ロジック、依存ゼロ）
3. `pdf.py`（img2pdf を使った純粋関数）
4. `window.py` / `capture.py` / `keys.py` / `preflight.py`（subprocess ラッパー）
5. `orchestrator.py`
6. `cli.py`
7. integration テストで実機確認
