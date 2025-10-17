# FILE: src/pixiv2epub/infrastructure/strategies/mappers.py

from html import escape
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ...models.fanbox import Post, PostBodyArticle, PostBodyText
from ...models.domain import Author, Identifier, NovelMetadata, PageInfo, SeriesInfo
from ...models.pixiv import NovelApiResponse
from ...models.workspace import Workspace
from ...shared.constants import IMAGES_DIR_NAME
from ..providers.pixiv.constants import PIXIV_NOVEL_URL
from .interfaces import IMetadataMapper
from .parsers import PixivTagParser


class PixivMetadataMapper(IMetadataMapper):
    """Pixiv APIのレスポンスをNovelMetadataにマッピングするクラス。"""

    def map_to_metadata(
        self,
        workspace: Workspace,
        cover_path: Optional[Path],
        **kwargs: Any,
    ) -> NovelMetadata:
        novel_data: NovelApiResponse = kwargs["novel_data"]
        detail_data: Dict = kwargs["detail_data"]
        parsed_text: str = kwargs["parsed_text"]
        parsed_description: str = kwargs["parsed_description"]

        novel = detail_data.get("novel", {})
        pages_content = parsed_text.split("[newpage]")
        author_info = Author(
            name=novel.get("user", {}).get("name"), id=novel.get("user", {}).get("id")
        )
        pages_info = [
            PageInfo(
                title=PixivTagParser.extract_page_title(content, i + 1),
                body=f"./page-{i + 1}.xhtml",
            )
            for i, content in enumerate(pages_content)
        ]

        series_order: Optional[int] = None
        if novel_data.series_id and novel_data.series_navigation:
            nav = novel_data.series_navigation
            if nav.prev_novel and nav.prev_novel.content_order:
                series_order = int(nav.prev_novel.content_order) + 1
            elif nav.next_novel:
                series_order = 1
            else:
                series_order = 1

        series_info_dict = novel.get("series")
        if series_info_dict and series_order:
            series_info_dict["order"] = series_order
        series_info = (
            SeriesInfo.model_validate(series_info_dict) if series_info_dict else None
        )

        relative_cover_path = (
            f"../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{cover_path.name}"
            if cover_path
            else None
        )

        return NovelMetadata(
            title=novel.get("title"),
            author=author_info,
            series=series_info,
            description=parsed_description,
            identifier=Identifier(novel_id=novel.get("id")),
            published_date=novel.get("create_date"),
            updated_date=novel.get("create_date"),  # Use create_date as a fallback
            cover_path=relative_cover_path,
            tags=[t.get("name") for t in novel.get("tags", [])],
            original_source=PIXIV_NOVEL_URL.format(novel_id=novel.get("id")),
            pages=pages_info,
            text_length=novel.get("text_length"),
        )


class FanboxMetadataMapper(IMetadataMapper):
    """Fanbox APIのレスポンスをNovelMetadataにマッピングするクラス。"""

    def map_to_metadata(
        self,
        workspace: Workspace,
        cover_path: Optional[Path],
        **kwargs: Any,
    ) -> NovelMetadata:
        post_data: Post = kwargs["post_data"]

        author_info = Author(name=post_data.user.name, id=int(post_data.user.user_id))
        pages_info = [PageInfo(title="本文", body="./page-1.xhtml")]
        relative_cover_path = (
            f"../{workspace.assets_path.name}/{IMAGES_DIR_NAME}/{cover_path.name}"
            if cover_path
            else None
        )
        source_url = (
            f"https://www.fanbox.cc/@{post_data.creator_id}/posts/{post_data.id}"
        )
        parsed_description = (
            escape(post_data.excerpt).replace("\n", "<br />")
            if post_data.excerpt
            else ""
        )
        body_text_length = self._get_body_text_length(post_data.body)

        return NovelMetadata(
            title=post_data.title,
            author=author_info,
            series=None,
            description=parsed_description,
            identifier=Identifier(
                post_id=post_data.id, creator_id=post_data.creator_id
            ),
            published_date=post_data.published_datetime,
            updated_date=post_data.updated_datetime,
            cover_path=relative_cover_path,
            tags=post_data.tags,
            original_source=source_url,
            pages=pages_info,
            text_length=body_text_length,
        )

    def _get_body_text_length(self, body: Union[PostBodyArticle, PostBodyText]) -> int:
        if isinstance(body, PostBodyText):
            return len(body.text or "")
        elif isinstance(body, PostBodyArticle):
            return sum(
                len(block.text or "") for block in body.blocks if hasattr(block, "text")
            )
        return 0
