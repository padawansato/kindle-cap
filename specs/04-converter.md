# Spec 04: フォーマット変換パイプライン

## 概要

Kindleファイルを EPUB/PDF に変換し、Calibreライブラリに登録する。

## モジュール

`kindle_calibre.core.converter.BookConverter`

## 依存

- `CalibreClient` (Spec 02)
- `ProcessedRegistry` (Spec 03)

## メソッド

### convert_one(file: KindleFile, formats: list[str]) -> ConversionReport

1冊の書籍を処理する。

```python
@dataclass
class ConversionReport:
    file: KindleFile
    calibre_id: int | None
    converted_formats: list[str]   # 成功したフォーマット
    failed_formats: list[str]      # 失敗したフォーマット
    skipped: bool                  # 処理済みスキップ
    error: str | None
```

処理フロー:
1. レジストリで処理済みチェック → スキップ
2. `CalibreClient.add_book()` でCalibreに追加
3. 各フォーマットについて `CalibreClient.convert_book()` → `add_format()`
4. レジストリに記録
5. 一時ファイルを削除

### convert_batch(files: list[KindleFile], formats: list[str], on_progress: Callback) -> BatchReport

複数書籍をバッチ処理する。

```python
@dataclass
class BatchReport:
    total: int
    success: int
    skipped: int
    failed: int
    reports: list[ConversionReport]
    elapsed_seconds: float
```

- `on_progress` コールバックで進捗を通知（CLIの進捗バー用）
- 1冊の失敗で全体を止めない（continue on error）
- 処理順はファイルサイズ昇順（小さいファイルから処理して早期フィードバック）

## 一時ファイル

変換中の一時ファイルは `/tmp/kindle-calibre/` に作成し、処理後に削除。
