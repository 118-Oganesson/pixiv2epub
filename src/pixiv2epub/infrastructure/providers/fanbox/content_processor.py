# FILE: src/pixiv2epub/infrastructure/providers/fanbox/content_processor.py
import shutil
from typing import Dict

from loguru import logger
from pydantic import ValidationError

from ....domain.interfaces import IFanboxImageDownloader
from ....models.domain import NovelMetadata
from ....models.fanbox import FanboxPostApiResponse, Post
from ....models.workspace import Workspace
from ....shared.constants import IMAGES_DIR_NAME
from ....shared.exceptions import DataProcessingError
from ...strategies.interfaces import (
    IContentParser,
    IMetadataMapper,
    IUpdateCheckStrategy,
)


class FanboxContentProcessor:
    """
    APIから取得したデータを処理し、ワークスペースを構築する責務を持つクラス。
    """

    def __init__(
        self,
        parser: IContentParser,
        mapper: IMetadataMapper,
        downloader: IFanboxImageDownloader,
        update_checker: IUpdateCheckStrategy,
    ):
        self.parser = parser
        self.mapper = mapper
        self.downloader = downloader
        self.update_checker = update_checker

    def check_for_updates(
        self, workspace: Workspace, raw_post_data: Dict
    ) -> tuple[bool, str]:
        """コンテンツの更新が必要かチェックし、必要ならワークスペースをクリーンアップします。"""
        post_data_body = raw_post_data.get("body", {})
        update_required, new_timestamp = self.update_checker.is_update_required(
            workspace, post_data_body
        )

        if update_required:
            logger.info("コンテンツの更新を検出、ダウンロードを続行します。")
            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)

        return update_required, new_timestamp

    def process_and_populate_workspace(
        self, workspace: Workspace, raw_post_data: Dict
    ) -> NovelMetadata:
        """
        コンテンツをパースし、画像をダウンロードし、XHTMLを保存し、
        最終的なメタデータを生成して返します。
        """
        try:
            post_data: Post = FanboxPostApiResponse.model_validate(raw_post_data).body

            image_dir = workspace.assets_path / IMAGES_DIR_NAME
            cover_path = self.downloader.download_cover(post_data, image_dir=image_dir)
            image_paths = self.downloader.download_embedded_images(
                post_data, image_dir=image_dir
            )

            parsed_html = self.parser.parse(post_data.body, image_paths)
            self._save_page(workspace, parsed_html)

            metadata = self.mapper.map_to_metadata(
                workspace=workspace, cover_path=cover_path, post_data=post_data
            )
            return metadata

        except (ValidationError, KeyError, TypeError) as e:
            raise DataProcessingError(
                f"投稿ID {workspace.id} のデータ解析に失敗: {e}", "fanbox"
            ) from e

    def _save_page(self, workspace: Workspace, parsed_html: str):
        """パースされた単一のXHTMLページを保存します。"""
        filename = workspace.source_path / "page-1.xhtml"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(parsed_html)
            logger.debug("1ページの保存が完了しました。")
        except IOError as e:
            logger.bind(error=str(e)).error("ページの保存に失敗しました。")
