"""book_ocr.writer の I/O テスト (tmp_path で副作用検証)."""

from __future__ import annotations

import json
from pathlib import Path

from book_ocr.models import PageText
from book_ocr.writer import write_outputs


def _page(n: int, body: str = "...") -> PageText:
    return PageText(
        page_number=n,
        png_path=Path(f"/tmp/page_{n:03d}.png"),
        markdown=body,
        ocr_engine="yomitoku",
    )


class TestWriteOutputs:
    def test_creates_out_dir_if_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "new-book"
        write_outputs(
            out_dir=target,
            book_md_filename="new-book.md",
            index={"title": "new-book", "pages": []},
            book_md="",
            pages=[],
        )
        assert target.is_dir()

    def test_writes_index_json(self, tmp_path: Path) -> None:
        write_outputs(
            out_dir=tmp_path,
            book_md_filename="my-book.md",
            index={"title": "my-book", "page_count": 0, "pages": []},
            book_md="",
            pages=[],
        )
        index_path = tmp_path / "index.json"
        assert index_path.exists()
        data = json.loads(index_path.read_text(encoding="utf-8"))
        assert data["title"] == "my-book"
        assert data["page_count"] == 0

    def test_writes_book_md_with_caller_filename(self, tmp_path: Path) -> None:
        write_outputs(
            out_dir=tmp_path,
            book_md_filename="custom-name.md",
            index={"pages": []},
            book_md="<!-- page:001 -->\n\nhello",
            pages=[],
        )
        assert (tmp_path / "custom-name.md").read_text(encoding="utf-8") == (
            "<!-- page:001 -->\n\nhello"
        )

    def test_writes_pages_md_files(self, tmp_path: Path) -> None:
        pages = [_page(1, "First"), _page(2, "Second")]
        write_outputs(
            out_dir=tmp_path,
            book_md_filename="my-book.md",
            index={"pages": []},
            book_md="",
            pages=pages,
        )
        assert (tmp_path / "pages" / "page_001.md").exists()
        assert (tmp_path / "pages" / "page_002.md").exists()

    def test_page_md_contains_marker_and_body(self, tmp_path: Path) -> None:
        pages = [_page(7, "本文の内容")]
        write_outputs(
            out_dir=tmp_path,
            book_md_filename="my-book.md",
            index={"pages": []},
            book_md="",
            pages=pages,
        )
        content = (tmp_path / "pages" / "page_007.md").read_text(encoding="utf-8")
        assert "<!-- page:007 -->" in content
        assert "本文の内容" in content

    def test_index_json_preserves_japanese_characters(self, tmp_path: Path) -> None:
        write_outputs(
            out_dir=tmp_path,
            book_md_filename="x.md",
            index={"title": "イシューからはじめよ", "pages": []},
            book_md="",
            pages=[],
        )
        raw = (tmp_path / "index.json").read_text(encoding="utf-8")
        assert "イシューからはじめよ" in raw
        # ensure_ascii=False が効いていること
        assert "\\u30a4" not in raw  # "イ" の Unicode escape が出ない

    def test_overwrites_existing_files(self, tmp_path: Path) -> None:
        (tmp_path / "old.md").write_text("old", encoding="utf-8")
        (tmp_path / "index.json").write_text("old", encoding="utf-8")

        write_outputs(
            out_dir=tmp_path,
            book_md_filename="new.md",
            index={"title": "new", "pages": []},
            book_md="new content",
            pages=[],
        )

        assert (tmp_path / "new.md").read_text(encoding="utf-8") == "new content"
        # index.json は上書きされる
        data = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
        assert data["title"] == "new"

    def test_creates_pages_subdir_when_pages_present(self, tmp_path: Path) -> None:
        write_outputs(
            out_dir=tmp_path,
            book_md_filename="x.md",
            index={"pages": []},
            book_md="",
            pages=[_page(1)],
        )
        assert (tmp_path / "pages").is_dir()

    def test_no_pages_subdir_when_pages_empty(self, tmp_path: Path) -> None:
        """空ページリストでは pages/ サブディレクトリを作らない (ノイズ削減)."""
        write_outputs(
            out_dir=tmp_path,
            book_md_filename="x.md",
            index={"pages": []},
            book_md="",
            pages=[],
        )
        assert not (tmp_path / "pages").exists()
