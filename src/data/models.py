from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, NamedTuple, Any


# --- compressor.py が利用するデータ構造 ---
@dataclass
class CompressionResult:
    """画像圧縮処理の結果を格納するデータクラス。"""

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


# --- builder.py とその分割クラスが利用するデータ構造 ---
class ImageAsset(NamedTuple):
    """EPUBに含める画像アセットの情報を格納するNamedTuple。"""

    id: str
    href: str
    path: Path
    media_type: str
    properties: str
    filename: str


class PageAsset(NamedTuple):
    """EPUBのページ（XHTML）の情報を格納するNamedTuple。"""

    id: str
    href: str
    content: bytes
    title: str


class EpubComponents(NamedTuple):
    """EPUB生成に必要な構成要素をまとめるNamedTuple。"""

    final_pages: List[PageAsset]
    final_images: List[ImageAsset]
    info_page: PageAsset
    cover_page: Optional[PageAsset]
    css_file_path: Optional[Path]
    content_opf: bytes
    nav_xhtml: bytes


@dataclass
class Author:
    """小説の作者情報を格納するデータクラス。"""

    name: str
    id: Optional[int] = None


@dataclass
class PageInfo:
    """detail.json内のページ情報を格納するデータクラス。"""

    title: str
    body_path: str  # ファイルパス

    @classmethod
    def from_dict(cls, data: dict) -> "PageInfo":
        return cls(title=data.get("title"), body_path=data.get("body"))


@dataclass
class SeriesInfo:
    """小説のシリーズ情報を格納するデータクラス。"""

    id: int
    title: str

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["SeriesInfo"]:
        if data and "id" in data and "title" in data:
            return cls(id=data["id"], title=data["title"])
        return None


@dataclass
class NovelMetadata:
    """detail.jsonの情報を格納するデータクラス。"""

    title: str
    authors: Author
    description: str
    tags: List[str]
    pages: List[PageInfo]
    cover_path: Optional[str]
    identifier: Dict[str, Any]
    date: str
    original_source: str
    series: Optional[SeriesInfo]
    text_length: Optional[int]

    @classmethod
    def from_dict(cls, data: dict) -> "NovelMetadata":
        return cls(
            title=data.get("title"),
            authors=Author(**data.get("authors", {})),
            description=data.get("description"),
            tags=data.get("tags", []),
            pages=[PageInfo.from_dict(p) for p in data.get("pages", [])],
            cover_path=data.get("cover"),
            identifier=data.get("identifier", {}),
            date=data.get("date"),
            original_source=data.get("original_source"),
            series=SeriesInfo.from_dict(data.get("series")),
            text_length=data.get("x_meta", {}).get("text_length"),
        )


# --- downloader.py が利用するAPI応答のデータ構造 ---


@dataclass
class Rating:
    """小説の評価情報を格納するデータクラス。"""

    like: int = 0
    bookmark: int = 0
    view: int = 0


@dataclass
class IllustTag:
    """挿絵イラストのタグ情報を格納するデータクラス。"""

    tag: str
    userId: Optional[str] = None


@dataclass
class IllustImageUrls:
    """挿絵イラストのURLを格納するデータクラス。"""

    small: Optional[str] = None
    medium: Optional[str] = None
    original: Optional[str] = None


@dataclass
class IllustDetails:
    """挿絵イラストの詳細情報を格納するデータクラス。"""

    title: str
    description: str
    restrict: int
    xRestrict: int
    sl: int
    tags: List[IllustTag] = field(default_factory=list)
    images: IllustImageUrls = field(default_factory=IllustImageUrls)


@dataclass
class IllustUser:
    """挿絵イラストの投稿者情報を格納するデータクラス。"""

    id: str
    name: str
    image: str


@dataclass
class PixivIllust:
    """挿絵イラスト（pixivimage）全体の情報を格納するデータクラス。"""

    id: str
    visible: bool
    page: int
    illust: IllustDetails
    user: IllustUser
    availableMessage: Optional[str] = None


@dataclass
class UploadedImageUrls:
    """小説内挿入画像（uploadedimage）のURLを格納するデータクラス。"""

    original: str
    # 他の解像度のURLも必要に応じて追加可能
    # "240mw": str, "480mw": str, "1200x1200": str, ...


@dataclass
class UploadedImage:
    """小説内挿入画像（uploadedimage）全体の情報を格納するデータクラス。"""

    novelImageId: str
    sl: str
    urls: UploadedImageUrls


@dataclass
class NovelApiResponse:
    """Pixiv API (webview_novel) からの応答全体を格納するデータクラス。"""

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
    marker: Optional[Any] = None
    seriesNavigation: Optional[Any] = None
    glossaryItems: List[Any] = field(default_factory=list)
    replaceableItemIds: List[Any] = field(default_factory=list)
    seasonalEffectAnimationUrls: Optional[Any] = None
    eventBanners: Optional[Any] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelApiResponse":
        """辞書からNovelApiResponseインスタンスを生成するファクトリメソッド"""
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

        # 必須でないフィールドは.get()で安全に取得
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
            marker=data.get("marker"),
            seriesNavigation=data.get("seriesNavigation"),
            glossaryItems=data.get("glossaryItems", []),
            replaceableItemIds=data.get("replaceableItemIds", []),
            seasonalEffectAnimationUrls=data.get("seasonalEffectAnimationUrls"),
            eventBanners=data.get("eventBanners"),
        )


# --- downloader.py (シリーズ) が利用するAPI応答のデータ構造 ---


@dataclass
class SeriesUser:
    """シリーズ情報の作者を表すデータクラス。"""

    id: int
    name: str


@dataclass
class SeriesDetail:
    """シリーズの詳細情報を格納するデータクラス。"""

    id: int
    title: str
    user: SeriesUser


@dataclass
class NovelInSeries:
    """シリーズ内の各小説の情報を格納するデータクラス。"""

    id: int
    title: str
    order: int


@dataclass
class NovelSeriesApiResponse:
    """Pixiv API (novel_series) からの応答全体を格納するデータクラス。"""

    detail: SeriesDetail
    novels: List[NovelInSeries]
    next_url: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelSeriesApiResponse":
        detail_data = data.get("novel_series_detail", {})
        user_data = detail_data.get("user", {})

        novels_data = []
        # **novel_dict のようにアンパックするのではなく、必要なキーだけを明示的に指定する
        for i, novel_dict in enumerate(data.get("novels", [])):
            novels_data.append(
                NovelInSeries(
                    id=novel_dict.get("id"),
                    title=novel_dict.get("title"),
                    order=novel_dict.get("order", i + 1),
                )
            )

        return cls(
            detail=SeriesDetail(
                id=detail_data.get("id"),
                title=detail_data.get("title"),
                user=SeriesUser(id=user_data.get("id"), name=user_data.get("name")),
            ),
            novels=novels_data,
            next_url=data.get("next_url"),
        )
