# FILE: src/pixiv2epub/models/local.py
"""
アプリケーションの内部処理（ビルド、画像圧縮など）で利用されるデータモデル。
外部APIの仕様とは独立しています。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, NamedTuple, Optional

from pydantic import BaseModel, Field


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
class ImageAsset(BaseModel, frozen=True):
    """EPUBに含める画像アセットの情報を管理します。"""

    id: str
    href: str
    path: Path
    media_type: str
    properties: str
    filename: str


class PageAsset(BaseModel, frozen=True):
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
    css_asset: Optional[PageAsset]
    content_opf: bytes
    nav_xhtml: bytes


# --- ローカルメタデータ (detail.json) 関連 ---
class Author(BaseModel):
    """小説の作者情報を格納します。"""

    name: str
    id: Optional[int] = None


class PageInfo(BaseModel):
    """`detail.json`内の各ページ（章）の情報を格納します。"""

    title: str
    body: str


class SeriesInfo(BaseModel):
    """小説のシリーズ情報を格納します。"""

    id: int
    title: str
    order: Optional[int] = None


class Identifier(BaseModel):
    """作品のユニークIDを格納するモデル。"""

    novel_id: Optional[int] = Field(None, alias="novel_id")
    post_id: Optional[str] = Field(None, alias="post_id")
    creator_id: Optional[str] = Field(None, alias="creator_id")
    uuid: Optional[str] = None


class NovelMetadata(BaseModel):
    """`detail.json`に記載された小説のメタデータ全体を格納します。"""

    title: str
    author: Author
    series: Optional[SeriesInfo]
    description: str
    identifier: Identifier
    published_date: str
    updated_date: Optional[str]
    cover_path: Optional[str]
    tags: List[str]
    original_source: str
    pages: List[PageInfo]
    text_length: Optional[int]
