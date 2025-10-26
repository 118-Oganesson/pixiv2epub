# FILE: src/pixiv2epub/models/domain.py
"""
アプリケーションのドメイン（関心領域）における中心的なデータモデルを定義します。
Unified Content Manifest (UCM) を中心とします。
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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


class EpubComponents(BaseModel):
    """EPUBファイルを生成するために必要な全ての構成要素をまとめます。"""

    model_config = ConfigDict(frozen=True)

    final_pages: List[PageAsset]
    final_images: List[ImageAsset]
    info_page: PageAsset
    cover_page: Optional[PageAsset]
    css_asset: Optional[PageAsset]
    content_opf: bytes
    nav_xhtml: bytes

# --- UCM (Unified Content Manifest) モデル ---
# detail.json の新しいスキーマ

class UCMBaseModel(BaseModel):
    # エイリアス名とフィールド名の両方で値を受け付ける
    model_config = ConfigDict(populate_by_name=True)

class UCMCoreAuthor(UCMBaseModel):
    """schema.org/Person に準拠した著者情報"""
    type_: str = Field("Person", alias="@type")
    name: str
    identifier: str # 例: "tag:pixiv.net,2007-09-10:user:87654321"

class UCMCoreSeries(UCMBaseModel):
    """schema.org/CreativeWorkSeries に準拠したシリーズ情報"""
    type_: str = Field("CreativeWorkSeries", alias="@type")
    name: str
    identifier: str # 例: "tag:pixiv.net,2007-09-10:series:112233"
    order: Optional[int] = None # シリーズ内の順序

class UCMCoreMetadata(UCMBaseModel):
    """コンテンツの核となるメタデータ (JSON-LD準拠)"""
    context_: Dict[str, str] = Field(..., alias="@context")
    type_: str = Field(..., alias="@type") # 例: "BlogPosting", "Article"
    id_: str = Field(..., alias="@id") # 正規ID (tag: URI)
    name: str # title
    author: UCMCoreAuthor
    isPartOf: Optional[UCMCoreSeries] = None # series
    datePublished: datetime
    dateModified: Optional[datetime] = None
    keywords: List[str] = Field(default_factory=list) # tags
    description: str
    mainEntityOfPage: HttpUrl # original_source
    image: Optional[str] = None # cover_pathの代わり (リソースキーを指す)

class UCMResource(UCMBaseModel):
    """リソースマニフェストのエントリ"""
    path: str # ワークスペース内の相対パス (例: "./assets/images/cover.jpg")
    mediaType: str # 例: "image/jpeg"
    role: str # 'cover', 'content', 'embeddedImage' など

class UCMContentBlock(UCMBaseModel):
    """コンテンツの論理構造"""
    type: str = "Page" # 構造のためシンプルなtype名を維持
    title: str
    source: str # リソースマニフェスト内のキー (例: "resource-page-1")

class UCMProviderData(UCMBaseModel):
    """プロバイダ固有のメタデータ (schema.org/PropertyValue)"""
    type_: str = Field("PropertyValue", alias="@type")
    propertyID: str # 例: "pixiv:textLength"
    value: Any

class UnifiedContentManifest(UCMBaseModel):
    """
    detail.json の新しいスキーマ。
    UCM (Unified Content Manifest)
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True) # populate_by_name を追加

    core: UCMCoreMetadata
    contentStructure: List[UCMContentBlock]
    resources: Dict[str, UCMResource]
    providerData: List[UCMProviderData] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "UnifiedContentManifest":
        """
        ワークスペースからdetail.jsonを読み込み、UCMを返します。

        Raises:
            FileNotFoundError: メタデータファイルが見つからない場合。
        """
        if not path.is_file():
            raise FileNotFoundError(f"メタデータファイルが見つかりません: {path}")
        # デフォルトでエイリアスを尊重する model_validate_json を使用
        return cls.model_validate_json(path.read_text(encoding="utf-8"))