# FILE: src/pixiv2epub/infrastructure/providers/fanbox/provider.py
import shutil
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from ....models.fanbox import FanboxPostApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import DownloadError
from ....shared.settings import Settings
from ..base_provider import BaseProvider
from ...strategies.mappers import FanboxMetadataMapper
from ...strategies.parsers import FanboxBlockParser
from ...strategies.update_checkers import TimestampUpdateStrategy
from .client import FanboxApiClient
from .downloader import FanboxImageDownloader


class FanboxProvider(BaseProvider):
    """Fanboxから投稿データを取得し、ワークスペースを生成するためのプロバイダ。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_client = FanboxApiClient(
            sessid=self.settings.providers.fanbox.sessid,
            api_delay=self.settings.downloader.api_delay,
            api_retries=self.settings.downloader.api_retries,
        )
        # Fanbox用の戦略オブジェクトをインスタンス化
        self.update_checker = TimestampUpdateStrategy(timestamp_key="updatedDatetime")
        self.parser = FanboxBlockParser()
        self.mapper = FanboxMetadataMapper()

    @classmethod
    def get_provider_name(cls) -> str:
        return "fanbox"

    def _save_page(self, workspace: Workspace, parsed_html: str):
        filename = workspace.source_path / "page-1.xhtml"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(parsed_html)
            logger.debug("1ページの保存が完了しました。")
        except IOError as e:
            logger.error(f"ページの保存に失敗しました: {e}")

    def get_post(self, post_id: Any) -> Workspace:
        logger.info(f"Fanbox 投稿ID: {post_id} の処理を開始します。")
        workspace = self._setup_workspace(post_id)

        try:
            post_data_dict = self.api_client.post_info(post_id)
            post_data_body = post_data_dict.get("body", {})

            update_required, new_timestamp = self.update_checker.is_update_required(
                workspace, post_data_body
            )
            if not update_required:
                logger.info(
                    f"コンテンツに変更はありません。処理をスキップします: {workspace.id}"
                )
                return workspace

            logger.info("コンテンツの更新を検出しました。ダウンロードを続行します。")
            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)

            post_data = FanboxPostApiResponse(**post_data_dict).body

            downloader = FanboxImageDownloader(
                api_client=self.api_client,
                image_dir=workspace.assets_path / "images",
                overwrite=self.settings.downloader.overwrite_existing_images,
            )
            cover_path = downloader.download_cover(post_data)
            image_paths = downloader.download_embedded_images(post_data)

            parsed_html = self.parser.parse(post_data.body, image_paths)
            self._save_page(workspace, parsed_html)

            metadata = self.mapper.map_to_metadata(
                workspace=workspace, cover_path=cover_path, post_data=post_data
            )

            manifest = WorkspaceManifest(
                provider_name=self.get_provider_name(),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                source_metadata={
                    "post_id": post_id,
                    "creator_id": post_data.creator_id,
                },
                content_hash=new_timestamp,
            )
            self._persist_metadata(workspace, metadata, manifest)

            logger.info(
                f"投稿「{post_data.title}」のデータ取得が完了しました -> {workspace.root_path}"
            )
            return workspace
        except Exception as e:
            logger.error(
                f"投稿ID {post_id} の処理中に予期せぬエラーが発生しました。",
                exc_info=True,
            )
            raise DownloadError(f"投稿ID {post_id} の処理に失敗しました: {e}") from e
