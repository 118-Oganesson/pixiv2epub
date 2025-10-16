# FILE: src/pixiv2epub/models/pixiv.py
"""
Pixiv APIのJSONレスポンスをマッピングするためのPydanticデータモデル。
このモジュールは外部APIの仕様に依存します。
"""

from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class PixivBaseModel(BaseModel):
    """すべてのPixivモデルで共通の設定を持つ基底クラス。"""

    model_config = ConfigDict(
        populate_by_name=True,  # エイリアス名とフィールド名の両方で値を受け付ける
        extra="ignore",  # モデルにない余分なフィールドは無視する
    )


# --- `webview_novel` APIレスポンスモデル ---
class Rating(PixivBaseModel):
    like: int = 0
    bookmark: int = 0
    view: int = 0


class IllustTag(PixivBaseModel):
    tag: str
    user_id: Optional[str] = Field(None, alias="userId")


class IllustImageUrls(PixivBaseModel):
    small: Optional[str] = None
    medium: Optional[str] = None
    original: Optional[str] = None


class IllustDetails(PixivBaseModel):
    title: str
    description: str
    restrict: int
    x_restrict: int = Field(alias="xRestrict")
    sl: int
    tags: List[IllustTag] = Field(default_factory=list)
    images: IllustImageUrls = Field(default_factory=IllustImageUrls)


class IllustUser(PixivBaseModel):
    id: str
    name: str
    image: str


class PixivIllust(PixivBaseModel):
    id: str
    visible: bool
    page: int
    illust: IllustDetails
    user: IllustUser
    available_message: Optional[str] = Field(None, alias="availableMessage")


class UploadedImageUrls(PixivBaseModel):
    original: str


class UploadedImage(PixivBaseModel):
    novel_image_id: str = Field(alias="novelImageId")
    sl: str
    urls: UploadedImageUrls


class SeriesNavigationNovel(PixivBaseModel):
    id: int
    content_order: str = Field(alias="contentOrder")
    viewable: bool
    title: str
    cover_url: str = Field(alias="coverUrl")
    viewable_message: Optional[str] = Field(None, alias="viewableMessage")


class SeriesNavigation(PixivBaseModel):
    next_novel: Optional[SeriesNavigationNovel] = Field(None, alias="nextNovel")
    prev_novel: Optional[SeriesNavigationNovel] = Field(None, alias="prevNovel")


class NovelApiResponse(PixivBaseModel):
    """Pixiv API (webview_novel) からの応答データ全体を格納します。"""

    id: str
    title: str
    user_id: str = Field(alias="userId")
    cover_url: str = Field(alias="coverUrl")
    caption: str
    cdate: str
    text: str
    ai_type: int = Field(alias="aiType")
    is_original: bool = Field(alias="isOriginal")
    tags: List[str] = Field(default_factory=list)
    rating: Rating = Field(default_factory=Rating)
    illusts: Dict[str, PixivIllust] = Field(default_factory=dict)
    images: Dict[str, UploadedImage] = Field(default_factory=dict)
    series_id: Optional[int] = Field(None, alias="seriesId")
    series_title: Optional[str] = Field(None, alias="seriesTitle")
    series_is_watched: Optional[bool] = Field(None, alias="seriesIsWatched")
    series_navigation: Optional[SeriesNavigation] = Field(
        None, alias="seriesNavigation"
    )

    @field_validator("illusts", "images", mode="before")
    @classmethod
    def empty_list_to_dict(cls, v: Any) -> Any:
        """APIが `illusts: []` や `images: []` のように空のリストを返す場合に対応する。"""
        if isinstance(v, list) and not v:
            return {}
        return v


# --- `novel_series` APIレスポンスモデル ---
class SeriesUser(PixivBaseModel):
    id: int
    name: str


class SeriesDetail(PixivBaseModel):
    id: int
    title: str
    user: SeriesUser


class NovelInSeries(PixivBaseModel):
    id: int
    title: str
    order: Optional[int] = None  # APIレスポンスに無いため、最初はOptionalとして定義


class NovelSeriesApiResponse(PixivBaseModel):
    """Pixiv API (novel_series) からの応答データ全体を格納します。"""

    novel_series_detail: SeriesDetail = Field(alias="novel_series_detail")
    novels: List[NovelInSeries]
    next_url: Optional[str] = Field(None, alias="next_url")

    @model_validator(mode="after")
    def assign_order_if_missing(self) -> "NovelSeriesApiResponse":
        """
        APIレスポンスに order がない場合、リストの順序に基づいて採番する。
        """
        for i, novel in enumerate(self.novels):
            if novel.order is None:
                novel.order = i + 1
        return self
