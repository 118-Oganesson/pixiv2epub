# FILE: src/pixiv2epub/models/fanbox.py
"""
FANBOX APIのJSONレスポンスをマッピングするためのPydanticデータモデル。
'article'形式（多様なブロックを含む）と'text'形式の両方に対応しています。
"""

from typing import Any, Dict, List, Literal, Optional, Union, Annotated
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FanboxBaseModel(BaseModel):
    """すべてのFanboxモデルで共通の設定を持つ基底クラス。"""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )


class FanboxUser(FanboxBaseModel):
    """投稿者のユーザー情報"""

    user_id: str = Field(..., alias="userId")
    name: str
    icon_url: HttpUrl = Field(..., alias="iconUrl")


# --- "article" 形式の本文ブロック定義 ---


class Style(FanboxBaseModel):
    """'p' ブロック内の太字などのスタイル情報"""

    type: str
    offset: int
    length: int


class Link(FanboxBaseModel):
    """'p' ブロック内のハイパーリンク情報"""

    url: HttpUrl
    offset: int
    length: int


class ParagraphBlock(FanboxBaseModel):
    """段落ブロック"""

    type: Literal["p"]
    text: str
    styles: Optional[List[Style]] = None
    links: Optional[List[Link]] = None


class HeaderBlock(FanboxBaseModel):
    """見出しブロック"""

    type: Literal["header"]
    text: str


class ImageBlock(FanboxBaseModel):
    """画像ブロック"""

    type: Literal["image"]
    image_id: str = Field(..., alias="imageId")


class FileBlock(FanboxBaseModel):
    """ファイル添付ブロック"""

    type: Literal["file"]
    file_id: str = Field(..., alias="fileId")


class UrlEmbedBlock(FanboxBaseModel):
    """URL埋め込みブロック"""

    type: Literal["url_embed"]
    url_embed_id: str = Field(..., alias="urlEmbedId")


BodyBlock = Annotated[
    Union[ParagraphBlock, HeaderBlock, ImageBlock, FileBlock, UrlEmbedBlock],
    Field(discriminator="type"),
]


class ImageMapItem(FanboxBaseModel):
    """imageMap内の画像アイテム"""

    id: str
    original_url: HttpUrl = Field(..., alias="originalUrl")
    thumbnail_url: HttpUrl = Field(..., alias="thumbnailUrl")
    width: int
    height: int
    extension: str


class FileMapItem(FanboxBaseModel):
    """fileMap内のファイルアイテム"""

    id: str
    name: str
    extension: str
    size: int
    url: HttpUrl


# --- urlEmbedMap内の多様な埋め込みアイテム定義 ---


class UrlEmbedPostInfo(FanboxBaseModel):
    """埋め込み投稿の簡易情報"""

    id: str
    title: str
    user: FanboxUser
    cover: Optional[Dict[str, Any]] = None
    excerpt: str


class UrlEmbedFanboxPost(FanboxBaseModel):
    """埋め込みアイテム: FANBOX投稿"""

    id: str
    type: Literal["fanbox.post"]
    post_info: UrlEmbedPostInfo = Field(..., alias="postInfo")


class CreatorProfile(FanboxBaseModel):
    """埋め込みクリエイターのプロフィール情報"""

    user: FanboxUser
    creator_id: str = Field(..., alias="creatorId")
    description: str
    has_adult_content: bool = Field(..., alias="hasAdultContent")
    cover_image_url: Optional[HttpUrl] = Field(None, alias="coverImageUrl")


class UrlEmbedFanboxCreator(FanboxBaseModel):
    """埋め込みアイテム: FANBOXクリエイター"""

    id: str
    type: Literal["fanbox.creator"]
    profile: CreatorProfile


class UrlEmbedHtmlCard(FanboxBaseModel):
    """埋め込みアイテム: 外部サイト (DLsiteなど)"""

    id: str
    type: Literal["html.card"]
    html: str


UrlEmbedMapItem = Annotated[
    Union[UrlEmbedFanboxPost, UrlEmbedFanboxCreator, UrlEmbedHtmlCard],
    Field(discriminator="type"),
]


class PostBodyArticle(FanboxBaseModel):
    """typeが "article" のときの本文"""

    blocks: List[BodyBlock] = Field(default_factory=list)
    image_map: Dict[str, ImageMapItem] = Field(default_factory=dict, alias="imageMap")
    file_map: Dict[str, FileMapItem] = Field(default_factory=dict, alias="fileMap")
    url_embed_map: Dict[str, UrlEmbedMapItem] = Field(
        default_factory=dict, alias="urlEmbedMap"
    )
    embed_map: Dict = Field(default_factory=dict, alias="embedMap")


class PostBodyText(FanboxBaseModel):
    """typeが "text" のときの本文"""

    text: str


class Post(FanboxBaseModel):
    """単一の投稿を表すメインモデル"""

    id: str
    title: str
    fee_required: int = Field(..., alias="feeRequired")
    published_datetime: str = Field(..., alias="publishedDatetime")
    updated_datetime: str = Field(..., alias="updatedDatetime")
    excerpt: str = ""
    user: FanboxUser
    creator_id: str = Field(..., alias="creatorId")
    cover_image_url: Optional[HttpUrl] = Field(None, alias="coverImageUrl")
    tags: List[str]
    body: Union[PostBodyArticle, PostBodyText]
    type: str


class FanboxPostApiResponse(FanboxBaseModel):
    """APIレスポンス全体をラップするモデル"""

    body: Post
