# FILE: src/pixiv2epub/infrastructure/providers/base_provider.py
import json
from dataclasses import asdict
from typing import Any

from loguru import logger
from pybreaker import CircuitBreaker

from ...domain.interfaces import IProvider
from ...models.domain import NovelMetadata
from ...models.workspace import Workspace, WorkspaceManifest
from ...shared.constants import DETAIL_FILE_NAME, MANIFEST_FILE_NAME, IMAGES_DIR_NAME
from ...shared.settings import Settings


class BaseProvider(IProvider):
    """プロバイダーの共通ワークフローを管理する抽象基底クラス。"""

    def __init__(self, settings: Settings, breaker: CircuitBreaker):
        """
        Args:
            settings (Settings): アプリケーション設定。
            breaker (CircuitBreaker): 共有サーキットブレーカーインスタンス。
        """
        self.settings = settings
        self.workspace_dir = settings.workspace.root_directory
        self._breaker: CircuitBreaker = breaker

        logger.bind(provider_name=self.__class__.__name__).info(
            "プロバイダーを初期化しました。"
        )

    @property
    def breaker(self) -> CircuitBreaker:
        """サーキットブレーカーのインスタンスを返します。"""
        return self._breaker

    def _setup_workspace(self, content_id: Any) -> Workspace:
        """content_idに基づいた永続的なワークスペースを準備します。"""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        provider_name = self.get_provider_name()
        workspace_id = f"{provider_name}_{content_id}"
        workspace_path = self.workspace_dir / workspace_id
        workspace = Workspace(id=workspace_id, root_path=workspace_path)

        workspace.source_path.mkdir(parents=True, exist_ok=True)
        (workspace.assets_path / IMAGES_DIR_NAME).mkdir(parents=True, exist_ok=True)

        logger.bind(workspace_path=str(workspace.root_path)).debug(
            "ワークスペースを準備しました。"
        )
        return workspace

    def _persist_metadata(
        self,
        workspace: Workspace,
        metadata: NovelMetadata,
        manifest: WorkspaceManifest,
    ):
        """メタデータとマニフェストをワークスペースに永続化します。"""
        # manifest.jsonの保存
        try:
            with open(workspace.manifest_path, "w", encoding="utf-8") as f:
                json.dump(asdict(manifest), f, ensure_ascii=False, indent=2)
            logger.debug(f"'{MANIFEST_FILE_NAME}' の保存が完了しました。")
        except IOError as e:
            logger.bind(error=str(e)).error(
                f"'{MANIFEST_FILE_NAME}' の保存に失敗しました。"
            )

        # detail.jsonの保存
        try:
            metadata_dict = metadata.model_dump(mode="json")
            detail_path = workspace.source_path / DETAIL_FILE_NAME
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            logger.debug(f"'{DETAIL_FILE_NAME}' の保存が完了しました。")
        except IOError as e:
            logger.bind(error=str(e)).error(
                f"'{DETAIL_FILE_NAME}' の保存に失敗しました。"
            )
