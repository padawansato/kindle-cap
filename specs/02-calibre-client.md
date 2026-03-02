# Spec 02: Calibre CLI クライアント

## 概要

CalibreのCLIツール（`calibredb`, `ebook-convert`）をラップし、Pythonから操作する。

## モジュール

`kindle_calibre.core.calibre.CalibreClient`

## コンストラクタ

```python
CalibreClient(
    calibredb_path: Path = Path("/Applications/calibre.app/Contents/MacOS/calibredb"),
    ebook_convert_path: Path = Path("/Applications/calibre.app/Contents/MacOS/ebook-convert"),
    library_path: Path = Path("~/Calibre Library").expanduser(),
)
```

- 指定パスにバイナリが存在しない場合は `CalibreNotFoundError` を送出
- `verify()` メソッドで接続確認可能

## メソッド

### add_book(file: Path) -> AddResult

`calibredb add` を実行してCalibreライブラリに書籍を追加する。

```python
@dataclass
class AddResult:
    success: bool
    book_id: int | None       # 追加された書籍のID
    duplicate: bool            # 重複していた場合 True
    error_message: str | None  # エラー時のメッセージ
```

- DeDRMプラグインにより自動でDRM解除される（Calibre側の設定に依存）
- 重複書籍の場合は `duplicate=True` で返す（エラーにしない）

### convert_book(book_id: int, output_format: str) -> ConvertResult

`ebook-convert` を実行して書籍を変換する。

```python
@dataclass
class ConvertResult:
    success: bool
    output_path: Path | None
    error_message: str | None
```

- `output_format` は `"epub"` または `"pdf"`
- 変換失敗時は `success=False` で返す（例外を投げない）

### add_format(book_id: int, file: Path) -> bool

`calibredb add_format` で既存書籍にフォーマットを追加する。

### list_books() -> list[CalibreBook]

`calibredb list` でライブラリ内の書籍一覧を取得する。

```python
@dataclass
class CalibreBook:
    id: int
    title: str
    authors: list[str]
    formats: list[str]   # ["EPUB", "PDF", "AZW3"] など
```

## エラーハンドリング

- subprocess のタイムアウト: デフォルト300秒（変換は時間がかかる場合がある）
- 戻り値の解析失敗 → `CalibreOutputParseError`
- Calibreプロセスの非ゼロ終了 → `CalibreCommandError`

## subprocess実行の原則

- `subprocess.run()` を使用（`shell=False`）
- `capture_output=True`, `text=True`
- すべての呼び出しをログに記録
