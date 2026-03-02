# Spec 03: 処理済みファイルレジストリ

## 概要

処理済みファイルを記録し、重複処理を防止する。

## モジュール

`kindle_calibre.core.registry.ProcessedRegistry`

## ストレージ

`~/.config/kindle-calibre/processed.json` にJSON形式で保存。

```json
{
  "version": 1,
  "entries": {
    "a1b2c3d4...": {
      "filename": "book.azw3",
      "processed_at": "2026-03-02T10:30:00",
      "calibre_id": 42,
      "formats": ["epub", "pdf"],
      "source": "kindle_mac"
    }
  }
}
```

キーはファイルのMD5ハッシュ。

## メソッド

### is_processed(file: KindleFile) -> bool

MD5ハッシュで処理済みかチェック。

### mark_processed(file: KindleFile, calibre_id: int, formats: list[str], source: str) -> None

処理済みとして記録。即座にファイルに永続化。

### get_stats() -> RegistryStats

```python
@dataclass
class RegistryStats:
    total_processed: int
    last_processed_at: datetime | None
    formats_count: dict[str, int]  # {"epub": 150, "pdf": 150}
```

### reset() -> None

全記録をクリア。確認プロンプトはCLI側で行う。

## 堅牢性

- ファイルが存在しない場合は空のレジストリを作成
- JSONが破損している場合はバックアップを作成してから空レジストリで初期化
- 書き込みはアトミック（tmpfileに書いてrenameする）
