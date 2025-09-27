# src/pixiv2epub/models/pixiv.py
"""
Pixiv APIのJSONレスポンスをマッピングするためのデータモデル。
このモジュールは外部APIの仕様に依存します。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --- `webview_novel` APIレスポンスモデル ---
@dataclass
class Rating:
    like: int = 0
    bookmark: int = 0
    view: int = 0


@dataclass
class IllustTag:
    tag: str
    userId: Optional[str] = None


@dataclass
class IllustImageUrls:
    small: Optional[str] = None
    medium: Optional[str] = None
    original: Optional[str] = None


@dataclass
class IllustDetails:
    title: str
    description: str
    restrict: int
    xRestrict: int
    sl: int
    tags: List[IllustTag] = field(default_factory=list)
    images: IllustImageUrls = field(default_factory=IllustImageUrls)


@dataclass
class IllustUser:
    id: str
    name: str
    image: str


@dataclass
class PixivIllust:
    id: str
    visible: bool
    page: int
    illust: IllustDetails
    user: IllustUser
    availableMessage: Optional[str] = None


@dataclass
class UploadedImageUrls:
    original: str


@dataclass
class UploadedImage:
    novelImageId: str
    sl: str
    urls: UploadedImageUrls


@dataclass
class SeriesNavigationNovel:
    """
    【修正点】
    APIレスポンスに含まれる他のキーもフィールドとして定義します。
    これにより "unexpected keyword argument" エラーが解消されます。
    """

    id: int
    contentOrder: str
    viewable: bool
    title: str
    coverUrl: str
    viewableMessage: Optional[str]


@dataclass
class SeriesNavigation:
    nextNovel: Optional[SeriesNavigationNovel] = None
    prevNovel: Optional[SeriesNavigationNovel] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["SeriesNavigation"]:
        if not data:
            return None
        return cls(
            nextNovel=SeriesNavigationNovel(**data["nextNovel"])
            if data.get("nextNovel")
            else None,
            prevNovel=SeriesNavigationNovel(**data["prevNovel"])
            if data.get("prevNovel")
            else None,
        )


@dataclass
class NovelApiResponse:
    """Pixiv API (webview_novel) からの応答データ全体を格納します。"""

    id: str
    title: str
    userId: str
    coverUrl: str
    caption: str
    cdate: str
    text: str
    aiType: int
    isOriginal: bool
    tags: List[str] = field(default_factory=list)
    rating: Rating = field(default_factory=Rating)
    illusts: Dict[str, PixivIllust] = field(default_factory=dict)
    images: Dict[str, UploadedImage] = field(default_factory=dict)
    seriesId: Optional[int] = None
    seriesTitle: Optional[str] = None
    seriesIsWatched: Optional[bool] = None
    seriesNavigation: Optional[SeriesNavigation] = None
    # ... (その他の未使用フィールドは省略しても良い)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelApiResponse":
        """API応答の辞書からインスタンスを安全に生成します。"""
        rating_data = data.get("rating", {})
        illusts_data = data.get("illusts", {})
        images_data = data.get("images", {})

        processed_illusts = {}
        if illusts_data:
            for illust_id, illust_val in illusts_data.items():
                illust_details_data = illust_val.get("illust", {})
                illust_tags = [
                    IllustTag(**tag) for tag in illust_details_data.get("tags", [])
                ]
                illust_images = IllustImageUrls(**illust_details_data.get("images", {}))
                processed_illusts[illust_id] = PixivIllust(
                    id=illust_val.get("id"),
                    visible=illust_val.get("visible"),
                    page=illust_val.get("page"),
                    illust=IllustDetails(
                        title=illust_details_data.get("title"),
                        description=illust_details_data.get("description"),
                        restrict=illust_details_data.get("restrict"),
                        xRestrict=illust_details_data.get("xRestrict"),
                        sl=illust_details_data.get("sl"),
                        tags=illust_tags,
                        images=illust_images,
                    ),
                    user=IllustUser(**illust_val.get("user", {})),
                )

        processed_images = {}
        if images_data:
            for image_id, image_val in images_data.items():
                urls_dict = image_val.get("urls", {})
                processed_urls = UploadedImageUrls(original=urls_dict.get("original"))
                processed_images[image_id] = UploadedImage(
                    novelImageId=image_val.get("novelImageId"),
                    sl=image_val.get("sl"),
                    urls=processed_urls,
                )

        return cls(
            id=data.get("id"),
            title=data.get("title"),
            userId=data.get("userId"),
            coverUrl=data.get("coverUrl"),
            tags=data.get("tags", []),
            caption=data.get("caption"),
            cdate=data.get("cdate"),
            rating=Rating(**rating_data),
            text=data.get("text"),
            illusts=processed_illusts,
            images=processed_images,
            aiType=data.get("aiType"),
            isOriginal=data.get("isOriginal"),
            seriesId=data.get("seriesId"),
            seriesTitle=data.get("seriesTitle"),
            seriesIsWatched=data.get("seriesIsWatched"),
            seriesNavigation=SeriesNavigation.from_dict(data.get("seriesNavigation")),
        )


# --- `novel_series` APIレスポンスモデル ---
@dataclass
class SeriesUser:
    id: int
    name: str


@dataclass
class SeriesDetail:
    id: int
    title: str
    user: SeriesUser


@dataclass
class NovelInSeries:
    id: int
    title: str
    order: int


@dataclass
class NovelSeriesApiResponse:
    """Pixiv API (novel_series) からの応答データ全体を格納します。"""

    detail: SeriesDetail
    novels: List[NovelInSeries]
    next_url: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelSeriesApiResponse":
        """API応答の辞書からインスタンスを安全に生成します。"""
        detail_data = data.get("novel_series_detail", {})
        user_data = detail_data.get("user", {})
        novels_data = [
            NovelInSeries(
                id=novel.get("id"),
                title=novel.get("title"),
                order=novel.get("order", i + 1),
            )
            for i, novel in enumerate(data.get("novels", []))
        ]
        return cls(
            detail=SeriesDetail(
                id=detail_data.get("id"),
                title=detail_data.get("title"),
                user=SeriesUser(id=user_data.get("id"), name=user_data.get("name")),
            ),
            novels=novels_data,
            next_url=data.get("next_url"),
        )
