# src/pixiv2epub/models/local.py
"""
アプリケーションの内部処理（ビルド、画像圧縮など）で利用されるデータモデル。
外部APIの仕様とは独立しています。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional


# --- 画像圧縮関連 ---
@dataclass
class CompressionResult:
    """画像圧縮処理の結果を格納します。"""

    input_path: Path
    output_path: Optional[Path]
    original_size: Optional[int]
    compressed_size: Optional[int]
    saved_bytes: Optional[int]
    saved_percent: Optional[float]
    tool: Optional[str]
    command: Optional[str]
    stdout: Optional[str]
    stderr: Optional[str]
    success: bool
    skipped: bool = False
    duration: Optional[float] = None
    output_bytes: Optional[bytes] = None


# --- EPUBビルド関連 ---
class ImageAsset(NamedTuple):
    """EPUBに含める画像アセットの情報を管理します。"""

    id: str
    href: str
    path: Path
    media_type: str
    properties: str
    filename: str


class PageAsset(NamedTuple):
    """EPUBの各ページ（XHTML）の情報を管理します。"""

    id: str
    href: str
    content: bytes
    title: str


class EpubComponents(NamedTuple):
    """EPUBファイルを生成するために必要な全ての構成要素をまとめます。"""

    final_pages: List[PageAsset]
    final_images: List[ImageAsset]
    info_page: PageAsset
    cover_page: Optional[PageAsset]
    css_file_path: Optional[Path]
    content_opf: bytes
    nav_xhtml: bytes


# --- ローカルメタデータ (detail.json) 関連 ---
@dataclass
class Author:
    """小説の作者情報を格納します。"""

    name: str
    id: Optional[int] = None


@dataclass
class PageInfo:
    """`detail.json`内の各ページ（章）の情報を格納します。"""

    title: str
    body: str

    @classmethod
    def from_dict(cls, data: dict) -> "PageInfo":
        return cls(title=data.get("title"), body=data.get("body"))


@dataclass
class SeriesInfo:
    """小説のシリーズ情報を格納します。"""

    id: int
    title: str

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["SeriesInfo"]:
        if data and "id" in data and "title" in data:
            return cls(id=data["id"], title=data["title"])
        return None


@dataclass
class NovelMetadata:
    """`detail.json`に記載された小説のメタデータ全体を格納します。"""

    title: str
    authors: Author
    series: Optional[SeriesInfo]
    description: str
    identifier: Dict[str, Any]
    date: str
    cover_path: Optional[str]
    tags: List[str]
    original_source: str
    pages: List[PageInfo]
    text_length: Optional[int]

    @classmethod
    def from_dict(cls, data: dict) -> "NovelMetadata":
        return cls(
            title=data.get("title"),
            authors=Author(**data.get("authors", {})),
            series=SeriesInfo.from_dict(data.get("series")),
            description=data.get("description"),
            identifier=data.get("identifier", {}),
            date=data.get("date"),
            cover_path=data.get("cover_path"),
            tags=data.get("tags", []),
            original_source=data.get("original_source"),
            pages=[PageInfo.from_dict(p) for p in data.get("pages", [])],
            text_length=data.get("text_length"),
        )
