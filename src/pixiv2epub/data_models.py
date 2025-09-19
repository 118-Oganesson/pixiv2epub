"""
アプリケーション全体で利用されるデータモデルを定義します。

このモジュールには、EPUB生成、画像圧縮、API通信など、
各機能コンポーネントで共通して使用されるデータ構造（データクラス、NamedTuple）
が集約されています。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, NamedTuple, Any


# --- compressor.py が利用するデータ構造 ---
@dataclass
class CompressionResult:
    """画像圧縮処理の結果を格納します。

    圧縮の成否、ファイルサイズの変化、実行したコマンドなど、
    処理に関する詳細な情報を保持します。

    Attributes:
        input_path (Path): 圧縮対象の画像ファイルパス。
        output_path (Optional[Path]): 圧縮後の画像ファイルパス。
        original_size (Optional[int]): 元のファイルサイズ（バイト）。
        compressed_size (Optional[int]): 圧縮後のファイルサイズ（バイト）。
        saved_bytes (Optional[int]): 削減されたファイルサイズ（バイト）。
        saved_percent (Optional[float]): 削減率（パーセント）。
        tool (Optional[str]): 使用した圧縮ツールの名前。
        command (Optional[str]): 実行したコマンドライン文字列。
        stdout (Optional[str]): 標準出力の内容。
        stderr (Optional[str]): 標準エラー出力の内容。
        success (bool): 圧縮が成功したかどうか。
        skipped (bool): 処理がスキップされたかどうか。
        duration (Optional[float]): 処理にかかった時間（秒）。
        output_bytes (Optional[bytes]): 圧縮後の画像データ本体。
    """

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
    """EPUBに含める画像アセットの情報を管理します。

    EPUBのOPFファイル（content.opf）内で<item>要素として定義される
    画像リソースに対応します。

    Attributes:
        id (str): 画像を一意に識別するためのID。
        href (str): EPUB内での画像の相対パス。
        path (Path): ローカルファイルシステム上の画像の絶対パス。
        media_type (str): 画像のMIMEタイプ（例: "image/jpeg"）。
        properties (str): EPUB 3のプロパティ（例: "cover-image"）。
        filename (str): 元のファイル名。
    """

    id: str
    href: str
    path: Path
    media_type: str
    properties: str
    filename: str


class PageAsset(NamedTuple):
    """EPUBの各ページ（XHTML）の情報を管理します。

    本文や目次などのXHTMLコンテンツを表現します。

    Attributes:
        id (str): ページを一意に識別するためのID。
        href (str): EPUB内でのページの相対パス。
        content (bytes): XHTMLコンテンツのバイト列。
        title (str): ページのタイトル。
    """

    id: str
    href: str
    content: bytes
    title: str


class EpubComponents(NamedTuple):
    """EPUBファイルを生成するために必要な全ての構成要素をまとめます。

    この構造体は、EPUBビルダーが最終的な.epubファイルを
    組み立てる際に利用します。

    Attributes:
        final_pages (List[PageAsset]): 本文となる全てのページアセットのリスト。
        final_images (List[ImageAsset]): EPUBに含まれる全ての画像アセットのリスト。
        info_page (PageAsset): 作品情報ページのアセット。
        cover_page (Optional[PageAsset]): 表紙ページのアセット。
        css_file_path (Optional[Path]): スタイルシート（CSS）ファイルのパス。
        content_opf (bytes): OPFファイル（content.opf）のコンテンツ。
        nav_xhtml (bytes): ナビゲーションファイル（nav.xhtml）のコンテンツ。
    """

    final_pages: List[PageAsset]
    final_images: List[ImageAsset]
    info_page: PageAsset
    cover_page: Optional[PageAsset]
    css_file_path: Optional[Path]
    content_opf: bytes
    nav_xhtml: bytes


@dataclass
class Author:
    """小説の作者情報を格納します。

    Attributes:
        name (str): 作者名。
        id (Optional[int]): 作者ID。
    """

    name: str
    id: Optional[int] = None


@dataclass
class PageInfo:
    """`detail.json`内の各ページ（章）の情報を格納します。

    Attributes:
        title (str): ページのタイトル（章題）。
        body (str): 本文テキストが格納されたファイルへのパス。
    """

    title: str
    body: str

    @classmethod
    def from_dict(cls, data: dict) -> "PageInfo":
        """辞書からPageInfoインスタンスを生成します。

        Args:
            data (dict): ページ情報を含む辞書。

        Returns:
            PageInfo: 生成されたPageInfoインスタンス。
        """
        return cls(title=data.get("title"), body=data.get("body"))


@dataclass
class SeriesInfo:
    """小説のシリーズ情報を格納します。

    Attributes:
        id (int): シリーズID。
        title (str): シリーズ名。
    """

    id: int
    title: str

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["SeriesInfo"]:
        """辞書からSeriesInfoインスタンスを生成します。

        Args:
            data (Optional[dict]): シリーズ情報を含む辞書。Noneの場合もあります。

        Returns:
            Optional[SeriesInfo]: 生成されたSeriesInfoインスタンス。
                                 データが無効な場合はNoneを返します。
        """
        if data and "id" in data and "title" in data:
            return cls(id=data["id"], title=data["title"])
        return None


@dataclass
class NovelMetadata:
    """`detail.json`に記載された小説のメタデータ全体を格納します。

    Attributes:
        title (str): 小説のタイトル。
        authors (Author): 作者情報。
        series (Optional[SeriesInfo]): シリーズ情報。
        description (str): あらすじ。
        identifier (Dict[str, Any]): 識別子情報（例: {"pixiv_id": 12345}）。
        date (str): 公開日。
        cover_path (Optional[str]): 表紙画像のファイルパス。
        tags (List[str]): タグのリスト。
        original_source (str): オリジナルのURL。
        pages (List[PageInfo]): 各ページの情報のリスト。
        text_length (Optional[int]): 本文の文字数。
    """

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
        """辞書からNovelMetadataインスタンスを生成します。

        Args:
            data (dict): `detail.json`から読み込んだメタデータを含む辞書。

        Returns:
            NovelMetadata: 生成されたNovelMetadataインスタンス。
        """
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


# --- downloader.py が利用するAPI応答のデータ構造 ---


@dataclass
class Rating:
    """小説の評価情報（いいね、ブックマーク、閲覧数）を格納します。

    Attributes:
        like (int): いいね数。
        bookmark (int): ブックマーク数。
        view (int): 閲覧数。
    """

    like: int = 0
    bookmark: int = 0
    view: int = 0


@dataclass
class IllustTag:
    """挿絵イラストに付けられたタグ情報を格納します。

    Attributes:
        tag (str): タグ名。
        userId (Optional[str]): タグを付けたユーザーのID。
    """

    tag: str
    userId: Optional[str] = None


@dataclass
class IllustImageUrls:
    """挿絵イラストの各種解像度のURLを格納します。

    Attributes:
        small (Optional[str]): サムネイル画像のURL。
        medium (Optional[str]): 中サイズ画像のURL。
        original (Optional[str]): オリジナル画像のURL。
    """

    small: Optional[str] = None
    medium: Optional[str] = None
    original: Optional[str] = None


@dataclass
class IllustDetails:
    """挿絵イラストの詳細情報を格納します。

    Attributes:
        title (str): イラストのタイトル。
        description (str): イラストの説明文（キャプション）。
        restrict (int): 閲覧制限のレベル。
        xRestrict (int): R-18などのより厳しい閲覧制限のレベル。
        sl (int): 謎のパラメータ。API仕様に依存。
        tags (List[IllustTag]): イラストのタグリスト。
        images (IllustImageUrls): イラストのURL情報。
    """

    title: str
    description: str
    restrict: int
    xRestrict: int
    sl: int
    tags: List[IllustTag] = field(default_factory=list)
    images: IllustImageUrls = field(default_factory=IllustImageUrls)


@dataclass
class IllustUser:
    """挿絵イラストの投稿者情報を格納します。

    Attributes:
        id (str): 投稿者のユーザーID。
        name (str): 投稿者の名前。
        image (str): 投稿者のプロフィール画像のURL。
    """

    id: str
    name: str
    image: str


@dataclass
class PixivIllust:
    """小説に関連付けられた挿絵イラスト（pixivimage）の全体情報を格納します。

    Attributes:
        id (str): イラストのID。
        visible (bool): イラストが可視状態か。
        page (int): イラストが属するページ番号。
        illust (IllustDetails): イラストの詳細情報。
        user (IllustUser): 投稿者のユーザー情報。
        availableMessage (Optional[str]): イラストが利用できない場合のメッセージ。
    """

    id: str
    visible: bool
    page: int
    illust: IllustDetails
    user: IllustUser
    availableMessage: Optional[str] = None


@dataclass
class UploadedImageUrls:
    """小説内に直接アップロードされた挿入画像のURLを格納します。

    Attributes:
        original (str): オリジナル解像度の画像URL。
        # APIの仕様変更で他の解像度が追加される可能性を考慮し、
        # `original` のみ必須として定義する。
    """

    original: str


@dataclass
class UploadedImage:
    """小説内に直接アップロードされた挿入画像（uploadedimage）の全体情報を格納します。

    Attributes:
        novelImageId (str): 小説内での画像ID。
        sl (str): 謎のパラメータ。API仕様に依存。
        urls (UploadedImageUrls): 画像のURL情報。
    """

    novelImageId: str
    sl: str
    urls: UploadedImageUrls


@dataclass
class NovelApiResponse:
    """Pixiv API (webview_novel) からの応答データ全体を格納します。

    小説本文、メタデータ、挿絵、評価など、全ての情報を含みます。

    Attributes:
        id (str): 小説ID。
        title (str): 小説タイトル。
        userId (str): 投稿者のユーザーID。
        coverUrl (str): 表紙画像のURL。
        caption (str): キャプション（概要）。
        cdate (str): 投稿日時。
        text (str): 小説の本文。
        aiType (int): AI生成作品かどうかのフラグ。
        isOriginal (bool): オリジナル作品かどうかのフラグ。
        tags (List[str]): タグのリスト。
        rating (Rating): 評価情報。
        illusts (Dict[str, PixivIllust]): 挿絵イラストの辞書（キーはイラストID）。
        images (Dict[str, UploadedImage]): 挿入画像の辞書（キーは画像ID）。
        seriesId (Optional[int]): シリーズID。
        seriesTitle (Optional[str]): シリーズタイトル。
        seriesIsWatched (Optional[bool]): シリーズをウォッチしているか。
        marker (Optional[Any]): 未使用または用途不明のフィールド。
        seriesNavigation (Optional[Any]): 未使用または用途不明のフィールド。
        glossaryItems (List[Any]): 未使用または用途不明のフィールド。
        replaceableItemIds (List[Any]): 未使用または用途不明のフィールド。
        seasonalEffectAnimationUrls (Optional[Any]): 未使用または用途不明のフィールド。
        eventBanners (Optional[Any]): 未使用または用途不明のフィールド。
    """

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
        """
        API応答の辞書からNovelApiResponseインスタンスを安全に生成します。

        ネストされた複雑な辞書構造を解析し、対応するデータクラスに変換します。
        キーが存在しない場合でも `KeyError` が発生しないように、
        `.get()` メソッドを利用して安全にアクセスします。

        Args:
            data (Dict[str, Any]): APIから返されたJSONをパースした辞書。

        Returns:
            NovelApiResponse: 生成されたNovelApiResponseインスタンス。
        """
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
    """シリーズ情報の作者を表します。

    Attributes:
        id (int): 作者のユーザーID。
        name (str): 作者名。
    """

    id: int
    name: str


@dataclass
class SeriesDetail:
    """シリーズの詳細情報を格納します。

    Attributes:
        id (int): シリーズID。
        title (str): シリーズタイトル。
        user (SeriesUser): 作者情報。
    """

    id: int
    title: str
    user: SeriesUser


@dataclass
class NovelInSeries:
    """シリーズに含まれる各小説の情報を格納します。

    Attributes:
        id (int): 小説ID。
        title (str): 小説タイトル。
        order (int): シリーズ内での順序。
    """

    id: int
    title: str
    order: int


@dataclass
class NovelSeriesApiResponse:
    """Pixiv API (novel_series) からの応答データ全体を格納します。

    Attributes:
        detail (SeriesDetail): シリーズ自体の詳細情報。
        novels (List[NovelInSeries]): シリーズに含まれる小説のリスト。
        next_url (Optional[str]): 続きのページがある場合のAPI URL。
    """

    detail: SeriesDetail
    novels: List[NovelInSeries]
    next_url: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelSeriesApiResponse":
        """
        API応答の辞書からNovelSeriesApiResponseインスタンスを安全に生成します。

        Args:
            data (Dict[str, Any]): APIから返されたJSONをパースした辞書。

        Returns:
            NovelSeriesApiResponse: 生成されたNovelSeriesApiResponseインスタンス。
        """
        detail_data = data.get("novel_series_detail", {})
        user_data = detail_data.get("user", {})

        novels_data = []
        for i, novel_dict in enumerate(data.get("novels", [])):
            novels_data.append(
                NovelInSeries(
                    id=novel_dict.get("id"),
                    title=novel_dict.get("title"),
                    # `order`キーが存在しない場合に備え、リストのインデックスをフォールバックとして使用する
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
