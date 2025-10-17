# FILE: src/pixiv2epub/infrastructure/providers/base_provider.py
import json
from dataclasses import asdict
from typing import Any, Optional

from loguru import logger
from pybreaker import CircuitBreaker

from ...models.local import NovelMetadata
from ...models.workspace import Workspace, WorkspaceManifest
from ...shared.settings import Settings
from .base import IProvider


class BaseProvider(IProvider):
    """プロバイダーの共通ワークフローを管理する抽象基底クラス。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.workspace_dir = settings.workspace.root_directory
        self._breaker: Optional[CircuitBreaker] = None

    @property
    def breaker(self) -> CircuitBreaker:
        """サーキットブレーカーのインスタンスを遅延初期化して返します。"""
        if self._breaker is None:
            self._breaker = CircuitBreaker(
                fail_max=self.settings.downloader.circuit_breaker.fail_max,
                reset_timeout=self.settings.downloader.circuit_breaker.reset_timeout,
            )
        return self._breaker

    def _setup_workspace(self, content_id: Any) -> Workspace:
        """content_idに基づいた永続的なワークスペースを準備します。"""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        provider_name = self.get_provider_name()
        workspace_id = f"{provider_name}_{content_id}"
        workspace_path = self.workspace_dir / workspace_id
        workspace = Workspace(id=workspace_id, root_path=workspace_path)

        workspace.source_path.mkdir(parents=True, exist_ok=True)
        (workspace.assets_path / "images").mkdir(parents=True, exist_ok=True)

        logger.debug("ワークスペースを準備しました: {}", workspace.root_path)
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
            logger.debug("manifest.json の保存が完了しました。")
        except IOError as e:
            logger.error("manifest.json の保存に失敗しました: {}", e)

        # detail.jsonの保存
        try:
            metadata_dict = metadata.model_dump(mode="json")
            detail_path = workspace.source_path / "detail.json"
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            logger.debug("detail.json の保存が完了しました。")
        except IOError as e:
            logger.error("detail.json の保存に失敗しました: {}", e)
