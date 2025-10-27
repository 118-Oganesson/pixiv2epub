# FILE: src/pixiv2epub/infrastructure/strategies/mappers.py

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, cast

from pydantic import HttpUrl

from ...models.domain import (
    UCMContentBlock,
    UCMCoreAuthor,
    UCMCoreMetadata,
    UCMCoreSeries,
    UCMProviderData,
    UCMResource,
    UnifiedContentManifest,
)
from ...models.fanbox import Post, PostBodyArticle, PostBodyText
from ...models.pixiv import NovelApiResponse
from ...models.workspace import Workspace
from ...shared.constants import IMAGES_DIR_NAME
from ...utils.common import get_media_type_from_filename
from ..providers.fanbox.constants import FANBOX_EPOCH
from ..providers.pixiv.constants import PIXIV_EPOCH, PIXIV_NOVEL_URL
from .interfaces import IMetadataMapper
from .parsers import PixivTagParser


class PixivMetadataMapper(IMetadataMapper):
    """Pixiv APIのレスポンスをUCMにマッピングするクラス。"""

    def map_to_metadata(
        self,
        workspace: Workspace,
        cover_path: Path | None,
        **kwargs: object,
    ) -> UnifiedContentManifest:
        """
        Pixiv API レスポンスを UCM (Unified Content Manifest) にマッピングします。

        Args:
            workspace: 対象のワークスペース。
            cover_path: ダウンロードされたカバー画像のパス (存在する場合)。
            **kwargs:
                novel_data (NovelApiResponse): `webview_novel` API のレスポンス。
                detail_data (Dict): `novel_detail` API のレスポンス。
                parsed_text (str): [newpage] で分割可能なパース済み本文HTML。
                parsed_description (str): パース済みの作品概要 (HTML)。
                image_paths (Dict[str, Path]): (新規) ダウンロードされた埋め込み画像。
        """

        novel_data: NovelApiResponse = cast(NovelApiResponse, kwargs['novel_data'])
        detail_data: dict[str, Any] = cast(dict[str, Any], kwargs['detail_data'])
        parsed_text: str = cast(str, kwargs['parsed_text'])
        parsed_description: str = cast(str, kwargs['parsed_description'])
        image_paths: dict[str, Path] = cast(
            dict[str, Path], kwargs.get('image_paths', {})
        )

        novel = detail_data.get('novel', {})
        # --- 1. IDとURLの定義 ---
        novel_id = novel.get('id')
        user_id = novel.get('user', {}).get('id')
        series_info_dict = novel.get('series')

        novel_tag_id = f'tag:pixiv.net,{PIXIV_EPOCH}:novel:{novel_id}'
        author_tag_id = f'tag:pixiv.net,{PIXIV_EPOCH}:user:{user_id}'
        source_url = PIXIV_NOVEL_URL.format(novel_id=novel_id)

        # --- 2. リソースマニフェストの構築 ---
        resources: dict[str, UCMResource] = {}
        cover_key = None
        if cover_path:
            cover_key = 'resource-cover-image'
            resources[cover_key] = UCMResource(
                path=f'../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{cover_path.name}',
                mediaType=get_media_type_from_filename(cover_path.name),
                role='cover',
            )
        for image_id, image_path in image_paths.items():
            resource_key = f'resource-embedded-image-{image_id}'
            resources[resource_key] = UCMResource(
                path=f'../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{image_path.name}',
                mediaType=get_media_type_from_filename(image_path.name),
                role='embeddedImage',
            )

        # --- 3. コンテンツ構造の構築 ---
        content_structure: list[UCMContentBlock] = []
        pages_content = parsed_text.split('[newpage]')
        for i, content in enumerate(pages_content):
            page_num = i + 1
            page_key = f'resource-page-{page_num}'
            page_path = f'./page-{page_num}.xhtml'  # source/ ディレクトリからの相対パス

            resources[page_key] = UCMResource(
                path=page_path, mediaType='application/xhtml+xml', role='content'
            )

            content_structure.append(
                UCMContentBlock(
                    title=PixivTagParser.extract_page_title(content, page_num),
                    source=page_key,
                )
            )
        series_order = novel_data.computed_series_order
        series_order_value = cast(int | None, series_order)
        series_core = None
        if series_info_dict:
            series_tag_id = (
                f'tag:pixiv.net,{PIXIV_EPOCH}:series:{series_info_dict.get("id")}'
            )
            # [FIX] mypy が Pydantic のエイリアス付きフィールドを認識できないため、type: ignore を追加
            series_core = UCMCoreSeries(
                type_='CreativeWorkSeries',  # type: ignore [call-arg]
                name=series_info_dict.get('title'),
                identifier=series_tag_id,
                order=series_order_value,
            )

        # [FIX] mypy が Pydantic のエイリアス付きフィールドを認識できないため、type: ignore を追加
        core_metadata = UCMCoreMetadata(
            context_={  # type: ignore [call-arg]
                '@vocab': 'https://schema.org/',
                'pixiv': 'https://www.pixiv.net/terms.php#',
            },
            type_='BlogPosting',
            id_=novel_tag_id,
            name=novel.get('title'),
            author=UCMCoreAuthor(
                type_='Person',  # type: ignore [call-arg]
                name=novel.get('user', {}).get('name'),
                identifier=author_tag_id,
            ),
            isPartOf=series_core,
            datePublished=novel.get('create_date'),
            dateModified=novel.get('create_date'),
            keywords=[t.get('name') for t in novel.get('tags', [])],
            description=parsed_description,
            mainEntityOfPage=HttpUrl(source_url),
            image=cover_key,
        )

        provider_data = [
            # [FIX] mypy が Pydantic のエイリアス付きフィールドを認識できないため、type: ignore を追加
            UCMProviderData(
                type_='PropertyValue',  # type: ignore [call-arg]
                propertyID='pixiv:textLength',
                value=novel.get('text_length'),
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
        cover_path: Path | None,
        **kwargs: object,
    ) -> UnifiedContentManifest:
        """
        Fanbox API レスポンス (Post オブジェクト) を UCM (Unified Content Manifest) にマッピングします。

        Args:
            workspace: 対象のワークスペース。
            cover_path: ダウンロードされたカバー画像のパス (存在する場合)。
            **kwargs:
                post_data (Post): `post.info` API から取得したPydanticモデル。
                image_paths (Dict[str, Path]): (新規) ダウンロードされた埋め込み画像。
        """

        post_data: Post = cast(Post, kwargs['post_data'])
        image_paths: dict[str, Path] = cast(
            dict[str, Path], kwargs.get('image_paths', {})
        )

        # --- 1. IDとURLの定義 ---
        author_id_str = post_data.creator_id
        post_id_str = post_data.id
        author_tag_id = f'tag:fanbox.cc,{FANBOX_EPOCH}:creator:{author_id_str}'
        post_tag_id = f'tag:fanbox.cc,{FANBOX_EPOCH}:post:{post_id_str}'
        source_url = f'https://{author_id_str}.fanbox.cc/posts/{post_id_str}'

        # --- 2. リソースマニフェストの構築 ---
        resources: dict[str, UCMResource] = {}
        cover_key = None
        if cover_path:
            cover_key = 'resource-cover-image'
            resources[cover_key] = UCMResource(
                path=f'../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{cover_path.name}',
                mediaType=get_media_type_from_filename(cover_path.name),
                role='cover',
            )
        for image_id, image_path in image_paths.items():
            resource_key = f'resource-embedded-image-{image_id}'
            resources[resource_key] = UCMResource(
                path=f'../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{image_path.name}',
                mediaType=get_media_type_from_filename(image_path.name),
                role='embeddedImage',
            )

        content_key = 'resource-page-1'
        resources[content_key] = UCMResource(
            path='./page-1.xhtml',  # source/ ディレクトリからの相対パス
            mediaType='application/xhtml+xml',
            role='content',
        )

        content_structure = [UCMContentBlock(title='本文', source=content_key)]

        # [FIX] mypy が Pydantic のエイリアス付きフィールドを認識できないため、type: ignore を追加
        core_metadata = UCMCoreMetadata(
            context_={  # type: ignore [call-arg]
                '@vocab': 'https://schema.org/',
                'fanbox': 'https://www.pixiv.net/terms.php#',
            },
            type_='BlogPosting',
            id_=post_tag_id,
            name=post_data.title,
            author=UCMCoreAuthor(
                type_='Person',  # type: ignore [call-arg]
                name=post_data.user.name,
                identifier=author_tag_id,
            ),
            isPartOf=None,  # Fanbox にはシリーズ概念なし
            datePublished=datetime.fromisoformat(post_data.published_datetime),
            dateModified=datetime.fromisoformat(post_data.updated_datetime),
            keywords=post_data.tags,
            description=escape(post_data.excerpt).replace('\n', '<br />'),
            mainEntityOfPage=HttpUrl(source_url),
            image=cover_key,
        )

        provider_data = [
            # [FIX] mypy が Pydantic のエイリアス付きフィールドを認識できないため、type: ignore を追加
            UCMProviderData(
                type_='PropertyValue',  # type: ignore [call-arg]
                propertyID='fanbox:feeRequired',
                value=post_data.fee_required,
            ),
            UCMProviderData(
                type_='PropertyValue',  # type: ignore [call-arg]
                propertyID='fanbox:textLength',
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

    def _get_body_text_length(self, body: PostBodyArticle | PostBodyText | None) -> int:
        if isinstance(body, PostBodyText):
            return len(body.text or '')
        elif isinstance(body, PostBodyArticle):
            return sum(
                len(block.text or '') for block in body.blocks if hasattr(block, 'text')
            )
        return 0  # body が None の場合を処理
