# FILE: src/pixiv2epub/infrastructure/strategies/mappers.py

from html import escape
from pathlib import Path
from typing import Any, Dict, Optional, Union, List

from ...models.domain import (
    UnifiedContentManifest,
    UCMCoreMetadata,
    UCMCoreAuthor,
    UCMCoreSeries,
    UCMResource,
    UCMContentBlock,
    UCMProviderData,
)
from ...models.fanbox import Post, PostBodyArticle, PostBodyText
from ...models.pixiv import NovelApiResponse
from ...models.workspace import Workspace
from ...shared.constants import IMAGES_DIR_NAME
from ..providers.pixiv.constants import PIXIV_NOVEL_URL
from .interfaces import IMetadataMapper
from .parsers import PixivTagParser

# --- Tag URI 用の定数 ---
PIXIV_EPOCH = "2007-09-10"
FANBOX_EPOCH = "2018-04-26"


def get_media_type_from_filename(filename: str) -> str:
    """ファイル名の拡張子からMIMEタイプを返します。"""
    ext = filename.lower().split(".")[-1]
    MEDIA_TYPES = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "xhtml": "application/xhtml+xml",
        "css": "text/css",
    }
    return MEDIA_TYPES.get(ext, "application/octet-stream")


class PixivMetadataMapper(IMetadataMapper):
    """Pixiv APIのレスポンスをUCMにマッピングするクラス。"""

    def map_to_metadata(
        self,
        workspace: Workspace,
        cover_path: Optional[Path],
        **kwargs: Any,
    ) -> UnifiedContentManifest:
        novel_data: NovelApiResponse = kwargs["novel_data"]
        detail_data: Dict = kwargs["detail_data"]
        parsed_text: str = kwargs["parsed_text"]
        parsed_description: str = kwargs["parsed_description"]

        novel = detail_data.get("novel", {})
        # pages_content はコンテンツ構造の構築時に使用

        # --- 1. IDとURLの定義 ---
        novel_id = novel.get("id")
        user_id = novel.get("user", {}).get("id")
        series_info_dict = novel.get("series")

        novel_tag_id = f"tag:pixiv.net,{PIXIV_EPOCH}:novel:{novel_id}"
        author_tag_id = f"tag:pixiv.net,{PIXIV_EPOCH}:user:{user_id}"
        source_url = PIXIV_NOVEL_URL.format(novel_id=novel_id)

        # --- 2. リソースマニフェストの構築 ---
        resources: Dict[str, UCMResource] = {}
        cover_key = None
        if cover_path:
            cover_key = "resource-cover-image"
            resources[cover_key] = UCMResource(
                path=f"../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{cover_path.name}",
                mediaType=get_media_type_from_filename(cover_path.name),
                role="cover",
            )
        # TODO: kwargs から image_paths を受け取り、埋め込み画像リソースをここに追加

        # --- 3. コンテンツ構造の構築 ---
        content_structure: List[UCMContentBlock] = []
        pages_content = parsed_text.split("[newpage]")
        for i, content in enumerate(pages_content):
            page_num = i + 1
            page_key = f"resource-page-{page_num}"
            page_path = f"./page-{page_num}.xhtml"  # source/ ディレクトリからの相対パス

            resources[page_key] = UCMResource(
                path=page_path, mediaType="application/xhtml+xml", role="content"
            )

            content_structure.append(
                UCMContentBlock(
                    title=PixivTagParser.extract_page_title(content, page_num),
                    source=page_key,
                )
            )

        # --- 4. コアメタデータの構築 ---
        series_order = novel_data.computed_series_order
        series_core = None
        if series_info_dict:
            series_tag_id = (
                f"tag:pixiv.net,{PIXIV_EPOCH}:series:{series_info_dict.get('id')}"
            )
            series_core = UCMCoreSeries(
                type_="CreativeWorkSeries",  # エイリアスではなくフィールド名を使用
                name=series_info_dict.get("title"),
                identifier=series_tag_id,
                order=series_order,
            )

        core_metadata = UCMCoreMetadata(
            context_={
                "@vocab": "https://schema.org/",
                "pixiv": "https://www.pixiv.net/terms.php#",
            },  # フィールド名を使用
            type_="BlogPosting",  # エイリアスではなくフィールド名を使用
            id_=novel_tag_id,  # エイリアスではなくフィールド名を使用
            name=novel.get("title"),
            author=UCMCoreAuthor(
                type_="Person",  # エイリアスではなくフィールド名を使用
                name=novel.get("user", {}).get("name"),
                identifier=author_tag_id,
            ),
            isPartOf=series_core,
            datePublished=novel.get("create_date"),
            dateModified=novel.get("create_date"),  # フォールバック
            keywords=[t.get("name") for t in novel.get("tags", [])],
            description=parsed_description,
            mainEntityOfPage=source_url,
            image=cover_key,
        )

        # --- 5. プロバイダ固有データの構築 ---
        provider_data = [
            UCMProviderData(
                type_="PropertyValue",  # エイリアスではなくフィールド名を使用
                propertyID="pixiv:textLength",
                value=novel.get("text_length"),
            )
            # 必要に応じて他の pixiv 固有データを追加
        ]

        return UnifiedContentManifest(
            core=core_metadata,
            contentStructure=content_structure,
            resources=resources,
            providerData=provider_data,
        )


class FanboxMetadataMapper(IMetadataMapper):
    """Fanbox APIのレスポンスをUCMにマッピングするクラス。"""

    def map_to_metadata(
        self,
        workspace: Workspace,
        cover_path: Optional[Path],
        **kwargs: Any,
    ) -> UnifiedContentManifest:
        post_data: Post = kwargs["post_data"]

        # --- 1. IDとURLの定義 ---
        author_id_str = post_data.creator_id
        post_id_str = post_data.id
        author_tag_id = f"tag:fanbox.cc,{FANBOX_EPOCH}:creator:{author_id_str}"
        post_tag_id = f"tag:fanbox.cc,{FANBOX_EPOCH}:post:{post_id_str}"
        source_url = f"https://{author_id_str}.fanbox.cc/posts/{post_id_str}"

        # --- 2. リソースマニフェストの構築 ---
        resources: Dict[str, UCMResource] = {}
        cover_key = None
        if cover_path:
            cover_key = "resource-cover-image"
            resources[cover_key] = UCMResource(
                path=f"../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{cover_path.name}",
                mediaType=get_media_type_from_filename(cover_path.name),
                role="cover",
            )

        content_key = "resource-page-1"
        resources[content_key] = UCMResource(
            path="./page-1.xhtml",  # source/ ディレクトリからの相対パス
            mediaType="application/xhtml+xml",
            role="content",
        )
        # TODO: kwargs から image_paths を受け取り、埋め込み画像リソースをここに追加

        # --- 3. コンテンツ構造の構築 ---
        content_structure = [UCMContentBlock(title="本文", source=content_key)]

        # --- 4. コアメタデータの構築 ---
        core_metadata = UCMCoreMetadata(
            context_={
                "@vocab": "https://schema.org/",
                "fanbox": "https://www.pixiv.net/terms.php#",
            },  # フィールド名を使用
            type_="BlogPosting",  # エイリアスではなくフィールド名を使用
            id_=post_tag_id,  # エイリアスではなくフィールド名を使用
            name=post_data.title,
            author=UCMCoreAuthor(
                type_="Person",  # エイリアスではなくフィールド名を使用
                name=post_data.user.name,
                identifier=author_tag_id,
            ),
            isPartOf=None,  # Fanbox にはシリーズ概念なし
            datePublished=post_data.published_datetime,
            dateModified=post_data.updated_datetime,
            keywords=post_data.tags,
            description=escape(post_data.excerpt).replace("\n", "<br />"),
            mainEntityOfPage=source_url,
            image=cover_key,
        )

        # --- 5. プロバイダ固有データの構築 ---
        provider_data = [
            UCMProviderData(
                type_="PropertyValue",  # エイリアスではなくフィールド名を使用
                propertyID="fanbox:feeRequired",
                value=post_data.fee_required,
            ),
            UCMProviderData(
                type_="PropertyValue",  # エイリアスではなくフィールド名を使用
                propertyID="fanbox:textLength",
                value=self._get_body_text_length(post_data.body),
            ),
            # 必要に応じて他の fanbox 固有データを追加
        ]

        return UnifiedContentManifest(
            core=core_metadata,
            contentStructure=content_structure,
            resources=resources,
            providerData=provider_data,
        )

    def _get_body_text_length(
        self, body: Union[PostBodyArticle, PostBodyText, None]
    ) -> int:
        if isinstance(body, PostBodyText):
            return len(body.text or "")
        elif isinstance(body, PostBodyArticle):
            return sum(
                len(block.text or "") for block in body.blocks if hasattr(block, "text")
            )
        return 0  # body が None の場合を処理
