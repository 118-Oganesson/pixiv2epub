# FILE: src/pixiv2epub/infrastructure/providers/fanbox/provider.py

import json
import shutil
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from ....models.fanbox import FanboxPostApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import DownloadError
from ....shared.settings import Settings
from ..base import IProvider
from .client import FanboxApiClient
from .downloader import FanboxImageDownloader
from .workspace_writer import FanboxWorkspaceWriter


class FanboxProvider(IProvider):
    """Fanboxから投稿データを取得し、ワークスペースを生成するためのプロバイダ。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_client = FanboxApiClient(
            sessid=self.settings.providers.fanbox.sessid,
            api_delay=self.settings.downloader.api_delay,
            api_retries=self.settings.downloader.api_retries,
        )
        self.workspace_dir = self.settings.workspace.root_directory

    @classmethod
    def get_provider_name(cls) -> str:
        return "fanbox"

    def _setup_workspace(self, post_id: Any) -> Workspace:
        """post_idに基づいた永続的なワークスペースを準備します。"""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        workspace_path = self.workspace_dir / f"fanbox_{post_id}"
        workspace = Workspace(id=f"fanbox_{post_id}", root_path=workspace_path)

        workspace.source_path.mkdir(parents=True, exist_ok=True)
        (workspace.assets_path / "images").mkdir(parents=True, exist_ok=True)

        logger.debug(f"ワークスペースを準備しました: {workspace.root_path}")
        return workspace

    def get_post(self, post_id: Any) -> Workspace:
        """単一の投稿を取得し、ローカルに保存します。"""
        logger.info(f"Fanbox 投稿ID: {post_id} の処理を開始します。")
        workspace = self._setup_workspace(post_id)

        try:
            # 1. APIから投稿データを取得
            post_data_dict = self.api_client.post_info(post_id)
            post_data = FanboxPostApiResponse(**post_data_dict).body
            new_updated_time = post_data.updated_datetime

            # 2. 更新チェック
            if workspace.manifest_path.exists():
                try:
                    with open(workspace.manifest_path, "r", encoding="utf-8") as f:
                        manifest_data = json.load(f)
                    old_updated_time = manifest_data.get("content_hash")
                    if old_updated_time == new_updated_time:
                        logger.info(
                            f"コンテンツに変更はありません。処理をスキップします: {workspace.id}"
                        )
                        return workspace
                    logger.info(
                        "コンテンツの更新を検出しました。ダウンロードを続行します。"
                    )
                except (json.JSONDecodeError, IOError):
                    logger.warning(
                        "manifest.jsonの読み込みに失敗しました。ダウンロードを続行します。"
                    )

            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)

            # 3. Downloaderを初期化して画像ダウンロードを実行
            image_dir = workspace.assets_path / "images"
            downloader = FanboxImageDownloader(
                api_client=self.api_client,
                image_dir=image_dir,
                overwrite=self.settings.downloader.overwrite_existing_images,
            )
            cover_path = downloader.download_cover(post_data)
            image_paths = downloader.download_embedded_images(post_data)

            # 4. ワークスペースのマニフェストを作成
            manifest = WorkspaceManifest(
                provider_name=self.get_provider_name(),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                source_metadata={
                    "post_id": post_id,
                    "creator_id": post_data.creator_id,
                },
                content_hash=new_updated_time,
            )

            # 5. Writerを呼び出してファイルに永続化
            writer = FanboxWorkspaceWriter(workspace, cover_path, image_paths)
            writer.persist(post_data, manifest)

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
