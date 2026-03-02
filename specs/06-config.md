# Spec 06: 設定管理

## 概要

ユーザー固有の設定を管理する。

## モジュール

`kindle_calibre.core.config.Config`

## 設定ファイル

`~/.config/kindle-calibre/config.toml`

```toml
[paths]
calibredb = "/Applications/calibre.app/Contents/MacOS/calibredb"
ebook_convert = "/Applications/calibre.app/Contents/MacOS/ebook-convert"
calibre_library = "~/Calibre Library"
kindle_mac_dir = "~/Library/Containers/com.amazon.Kindle/Data/Library/Application Support/Kindle/My Kindle Content"
kindle_device_dir = "/Volumes/Kindle/documents"

[conversion]
output_formats = ["epub", "pdf"]
timeout_seconds = 300

[general]
log_level = "info"
```

## メソッド

### Config.load(path: Path | None = None) -> Config

- path未指定時はデフォルトパスを使用
- ファイルが存在しない場合はデフォルト値で作成
- TOML解析失敗時は `ConfigParseError`

### Config.save() -> None

現在の設定をファイルに保存。

### Config.get(key: str) -> Any

ドット記法でアクセス: `config.get("paths.calibredb")`

### Config.set(key: str, value: Any) -> None

値を設定して即座に永続化。

## デフォルト値

すべてのキーにデフォルト値が定義されている。
設定ファイルが存在しなくてもツールは動作する。
