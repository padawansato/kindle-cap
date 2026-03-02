"""CLI entry point (Spec 05).

Click-based CLI for Kindle to Calibre import tool.
"""

from __future__ import annotations

import click


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="詳細ログ")
@click.option("--quiet", "-q", is_flag=True, help="最小出力")
@click.option("--config", "config_path", type=click.Path(), default=None, help="設定ファイルパス")
@click.pass_context
def main(ctx: click.Context, verbose: bool, quiet: bool, config_path: str | None) -> None:
    """Kindle書籍をCalibreに一括インポート・管理するツール."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["config_path"] = config_path


@main.command(name="import")
@click.option("--source", type=click.Choice(["mac", "device", "both"]), default="mac")
@click.option("--formats", default="epub,pdf", help="出力フォーマット（カンマ区切り）")
@click.option("--dry-run", is_flag=True, help="処理対象の確認のみ")
@click.option("--yes", "-y", is_flag=True, help="確認プロンプトをスキップ")
@click.pass_context
def import_cmd(ctx: click.Context, source: str, formats: str, dry_run: bool, yes: bool) -> None:
    """既存のKindle書籍を一括インポート."""
    raise NotImplementedError("TODO: implement import command")


@main.command()
@click.option("--source", type=click.Choice(["mac", "device", "both"]), default="mac")
@click.option("--formats", default="epub,pdf", help="出力フォーマット（カンマ区切り）")
@click.argument("file", required=False, type=click.Path(exists=True))
@click.pass_context
def add(ctx: click.Context, source: str, formats: str, file: str | None) -> None:
    """新規購入書籍をCalibreに追加."""
    raise NotImplementedError("TODO: implement add command")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """処理状況を表示."""
    raise NotImplementedError("TODO: implement status command")


@main.group()
def config() -> None:
    """設定の確認・変更."""
    pass


@config.command(name="show")
def config_show() -> None:
    """設定一覧を表示."""
    raise NotImplementedError("TODO: implement config show")


@config.command(name="set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """設定値を変更."""
    raise NotImplementedError("TODO: implement config set")


@main.command()
@click.option("--yes", "-y", is_flag=True, help="確認プロンプトをスキップ")
def reset(yes: bool) -> None:
    """処理済みログをリセット."""
    raise NotImplementedError("TODO: implement reset command")


if __name__ == "__main__":
    main()
