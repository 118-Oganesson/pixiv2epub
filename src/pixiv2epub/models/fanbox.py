# FILE: src/pixiv2epub/models/fanbox.py
"""
FANBOX APIのJSONレスポンスをマッピングするためのPydanticデータモデル。
'article'形式（多様なブロックを含む）と'text'形式の両方に対応しています。
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, HttpUrl


class FanboxUser(BaseModel):
    """投稿者のユーザー情報"""

    user_id: str = Field(..., alias="userId")
    name: str
    icon_url: HttpUrl = Field(..., alias="iconUrl")


# --- "article" 形式の本文ブロック定義 ---


class Style(BaseModel):
    """'p' ブロック内の太字などのスタイル情報"""

    type: str
    offset: int
    length: int


class Link(BaseModel):
    """'p' ブロック内のハイパーリンク情報"""

    url: HttpUrl
    offset: int
    length: int


class ParagraphBlock(BaseModel):
    """段落ブロック"""

    type: Literal["p"]
    text: str
    styles: Optional[List[Style]] = None
    links: Optional[List[Link]] = None


class HeaderBlock(BaseModel):
    """見出しブロック"""

    type: Literal["header"]
    text: str


class ImageBlock(BaseModel):
    """画像ブロック"""

    type: Literal["image"]
    image_id: str = Field(..., alias="imageId")


class FileBlock(BaseModel):
    """ファイル添付ブロック"""

    type: Literal["file"]
    file_id: str = Field(..., alias="fileId")


class UrlEmbedBlock(BaseModel):
    """URL埋め込みブロック"""

    type: Literal["url_embed"]
    url_embed_id: str = Field(..., alias="urlEmbedId")


# 本文を構成するブロックの型をUnionで定義
BodyBlock = Union[
    ParagraphBlock,
    HeaderBlock,
    ImageBlock,
    FileBlock,
    UrlEmbedBlock,
]


class ImageMapItem(BaseModel):
    """imageMap内の画像アイテム"""

    id: str
    original_url: HttpUrl = Field(..., alias="originalUrl")
    thumbnail_url: HttpUrl = Field(..., alias="thumbnailUrl")
    width: int
    height: int
    extension: str


class FileMapItem(BaseModel):
    """fileMap内のファイルアイテム"""

    id: str
    name: str
    extension: str
    size: int
    url: HttpUrl


# --- urlEmbedMap内の多様な埋め込みアイテム定義 ---


class UrlEmbedPostInfo(BaseModel):
    """埋め込み投稿の簡易情報"""

    id: str
    title: str
    user: FanboxUser
    cover: Optional[Dict[str, Any]] = None
    excerpt: str


class UrlEmbedFanboxPost(BaseModel):
    """埋め込みアイテム: FANBOX投稿"""

    id: str
    type: Literal["fanbox.post"]
    post_info: UrlEmbedPostInfo = Field(..., alias="postInfo")


class CreatorProfile(BaseModel):
    """埋め込みクリエイターのプロフィール情報"""

    user: FanboxUser
    creator_id: str = Field(..., alias="creatorId")
    description: str
    has_adult_content: bool = Field(..., alias="hasAdultContent")
    cover_image_url: Optional[HttpUrl] = Field(None, alias="coverImageUrl")


class UrlEmbedFanboxCreator(BaseModel):
    """埋め込みアイテム: FANBOXクリエイター"""

    id: str
    type: Literal["fanbox.creator"]
    profile: CreatorProfile


class UrlEmbedHtmlCard(BaseModel):
    """埋め込みアイテム: 外部サイト (DLsiteなど)"""

    id: str
    type: Literal["html.card"]
    html: str


# urlEmbedMapのアイテム型をUnionで定義
UrlEmbedMapItem = Union[
    UrlEmbedFanboxPost,
    UrlEmbedFanboxCreator,
    UrlEmbedHtmlCard,
]


class PostBodyArticle(BaseModel):
    """typeが "article" のときの本文"""

    blocks: List[BodyBlock] = Field(default_factory=list, discriminator="type")
    image_map: Dict[str, ImageMapItem] = Field(default_factory=dict, alias="imageMap")
    file_map: Dict[str, FileMapItem] = Field(default_factory=dict, alias="fileMap")
    url_embed_map: Dict[str, UrlEmbedMapItem] = Field(
        default_factory=dict,
        alias="urlEmbedMap",
        discriminator="type",
    )
    embed_map: Dict = Field(default_factory=dict, alias="embedMap")


class PostBodyText(BaseModel):
    """typeが "text" のときの本文"""

    text: str


class Post(BaseModel):
    """単一の投稿を表すメインモデル"""

    id: str
    title: str
    fee_required: int = Field(..., alias="feeRequired")
    published_datetime: str = Field(..., alias="publishedDatetime")
    updated_datetime: str = Field(..., alias="updatedDatetime")
    user: FanboxUser
    creator_id: str = Field(..., alias="creatorId")
    cover_image_url: Optional[HttpUrl] = Field(None, alias="coverImageUrl")
    tags: List[str]
    body: Union[PostBodyArticle, PostBodyText]
    type: str

    class Config:
        populate_by_name = True


class FanboxPostApiResponse(BaseModel):
    """APIレスポンス全体をラップするモデル"""

    body: Post
