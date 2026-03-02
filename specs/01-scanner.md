# Spec 01: Kindle ファイルスキャナー

## 概要

指定ディレクトリからKindle書籍ファイル（.azw, .azw3, .kfx, .mobi）を検出する。

## モジュール

`kindle_calibre.core.scanner.KindleScanner`

## 振る舞い

### scan(directory: Path) -> list[KindleFile]

- 指定ディレクトリを再帰的に検索し、Kindleファイルを返す
- 対象拡張子: `.azw`, `.azw3`, `.kfx`, `.mobi`
- 大文字・小文字を区別しない（`.AZW3` も検出する）
- シンボリックリンクは追跡しない
- 隠しディレクトリ（`.`始まり）はスキップ
- ディレクトリが存在しない場合は `DirectoryNotFoundError` を送出

### scan_multiple(directories: list[Path]) -> list[KindleFile]

- 複数ディレクトリをスキャンして結果をマージ
- 重複ファイル（同一パス）は除去
- 存在しないディレクトリはスキップ（ログに警告を出力）

## データモデル

```python
@dataclass
class KindleFile:
    path: Path           # ファイルの絶対パス
    format: str          # "azw", "azw3", "kfx", "mobi"
    size_bytes: int      # ファイルサイズ
    modified_at: datetime # 最終更新日時
    md5_hash: str        # MD5ハッシュ（処理済み判定用）
```

## デフォルトスキャン先

| ソース | macOSパス |
|--------|----------|
| Kindle for Mac | `~/Library/Containers/com.amazon.Kindle/Data/Library/Application Support/Kindle/My Kindle Content` |
| Kindle端末 | `/Volumes/Kindle/documents` |

## エッジケース

- 空ディレクトリ → 空リストを返す
- 権限なしファイル → スキップしてログに警告
- 破損ファイル（0バイト） → スキップしてログに警告
