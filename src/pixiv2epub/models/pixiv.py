# FILE: src/pixiv2epub/models/pixiv.py
"""
Pixiv APIのJSONレスポンスをマッピングするためのPydanticデータモデル。
このモジュールは外部APIの仕様に依存します。
このモジュールはインフラストラクチャ層の一部であり、ドメイン層から
直接インポートしてはいけません。
"""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    computed_field,
    field_validator,
    model_validator,
)


class PixivBaseModel(BaseModel):
    """すべてのPixivモデルで共通の設定を持つ基底クラス。"""

    model_config = ConfigDict(
        populate_by_name=True,  # エイリアス名とフィールド名の両方で値を受け付ける
        extra='ignore',  # モデルにない余分なフィールドは無視する
    )


# --- `webview_novel` APIレスポンスモデル ---
class Rating(PixivBaseModel):
    like: int = 0
    bookmark: int = 0
    view: int = 0


class IllustTag(PixivBaseModel):
    tag: str
    user_id: str | None = Field(None, alias='userId')


class IllustImageUrls(PixivBaseModel):
    small: HttpUrl | None = None
    medium: HttpUrl | None = None
    original: HttpUrl | None = None


class IllustDetails(PixivBaseModel):
    title: str
    description: str
    restrict: int
    x_restrict: int = Field(alias='xRestrict')
    sl: int
    tags: list[IllustTag] = Field(default_factory=list)
    images: IllustImageUrls = Field(default_factory=IllustImageUrls)


class IllustUser(PixivBaseModel):
    id: str
    name: str
    image: HttpUrl


class PixivIllust(PixivBaseModel):
    id: str
    visible: bool
    page: int
    illust: IllustDetails
    user: IllustUser
    available_message: str | None = Field(None, alias='availableMessage')


class UploadedImageUrls(PixivBaseModel):
    original: HttpUrl


class UploadedImage(PixivBaseModel):
    novel_image_id: str = Field(alias='novelImageId')
    sl: str
    urls: UploadedImageUrls


class SeriesNavigationNovel(PixivBaseModel):
    id: int
    content_order: str = Field(alias='contentOrder')
    viewable: bool
    title: str
    cover_url: HttpUrl = Field(alias='coverUrl')
    viewable_message: str | None = Field(None, alias='viewableMessage')


class SeriesNavigation(PixivBaseModel):
    next_novel: SeriesNavigationNovel | None = Field(None, alias='nextNovel')
    prev_novel: SeriesNavigationNovel | None = Field(None, alias='prevNovel')


class NovelApiResponse(PixivBaseModel):
    """Pixiv API (webview_novel) からの応答データ全体を格納します。"""

    id: str
    title: str
    user_id: str = Field(alias='userId')
    cover_url: HttpUrl = Field(alias='coverUrl')
    caption: str
    cdate: str
    text: str
    ai_type: int = Field(alias='aiType')
    is_original: bool = Field(alias='isOriginal')
    tags: list[str] = Field(default_factory=list)
    rating: Rating = Field(default_factory=Rating)
    illusts: dict[str, PixivIllust] = Field(default_factory=dict)
    images: dict[str, UploadedImage] = Field(default_factory=dict)
    series_id: int | None = Field(None, alias='seriesId')
    series_title: str | None = Field(None, alias='seriesTitle')
    series_is_watched: bool | None = Field(None, alias='seriesIsWatched')
    series_navigation: SeriesNavigation | None = Field(None, alias='seriesNavigation')

    @field_validator('illusts', 'images', mode='before')
    @classmethod
    def empty_list_to_dict(cls, v: object) -> object:
        """APIが `illusts: []` や `images: []` のように空のリストを返す場合に対応する。"""
        if isinstance(v, list) and not v:
            return {}
        return v

    @computed_field
    @property
    def computed_series_order(self) -> int | None:
        """series_navigationデータからシリーズ内の順序を導出します。"""
        if not self.series_id or not self.series_navigation:
            return None

        nav = self.series_navigation
        try:
            # 前の作品が存在する場合、その作品の content_order から次の順序を計算
            if nav.prev_novel and nav.prev_novel.content_order:
                return int(nav.prev_novel.content_order) + 1
            # 前の作品がなく、次の作品がある場合はシリーズの最初の作品
            elif nav.next_novel:
                return 1
            # 前後どちらの作品もない場合 (シリーズにこの作品しかない場合)
            else:
                return 1
        except (ValueError, TypeError):
            # content_order が予期せぬ形式だった場合のエラーハンドリング
            return None


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
    order: int | None = None  # APIレスポンスに無いため、最初はOptionalとして定義


class NovelSeriesApiResponse(PixivBaseModel):
    """Pixiv API (novel_series) からの応答データ全体を格納します。"""

    novel_series_detail: SeriesDetail = Field(alias='novel_series_detail')
    novels: list[NovelInSeries]
    next_url: HttpUrl | None = Field(None, alias='next_url')

    @model_validator(mode='after')
    def assign_order_if_missing(self) -> 'NovelSeriesApiResponse':
        """
        APIレスポンスに order がない場合、リストの順序に基づいて採番する。
        """
        for i, novel in enumerate(self.novels):
            if novel.order is None:
                novel.order = i + 1
        return self
