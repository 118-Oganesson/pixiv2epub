# FILE: src/pixiv2epub/infrastructure/repositories/filesystem.py
import json
from dataclasses import asdict
from typing import Any
from pathlib import Path

from loguru import logger

from ...domain.interfaces import IWorkspaceRepository
from ...models.domain import UnifiedContentManifest
from ...models.workspace import Workspace, WorkspaceManifest
from ...shared.constants import (
    ASSETS_DIR_NAME,
    DETAIL_FILE_NAME,
    IMAGES_DIR_NAME,
    MANIFEST_FILE_NAME,
    SOURCE_DIR_NAME,
)
from ...shared.settings import WorkspaceSettings


class FileSystemWorkspaceRepository(IWorkspaceRepository):
    """ファイルシステムを永続化層として使用するワークスペースリポジトリ。"""

    def __init__(self, settings: WorkspaceSettings):
        self.workspace_dir = settings.root_directory

    def setup_workspace(self, content_id: Any, provider_name: str) -> Workspace:
        """content_idに基づいた永続的なワークスペースを準備します。"""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        workspace_id = f"{provider_name}_{content_id}"
        workspace_path = self.workspace_dir / workspace_id
        workspace = Workspace(id=workspace_id, root_path=workspace_path)

        workspace.root_path.mkdir(parents=True, exist_ok=True)
        (workspace.root_path / SOURCE_DIR_NAME).mkdir(parents=True, exist_ok=True)
        (workspace.root_path / ASSETS_DIR_NAME / IMAGES_DIR_NAME).mkdir(
            parents=True, exist_ok=True
        )

        logger.bind(workspace_path=str(workspace.root_path)).debug(
            "ワークスペースを準備しました。"
        )
        return workspace

    def get_workspace_path(self, content_id: Any, provider_name: str) -> Path:
        """ワークスペースのルートパスを計算して返します（ディレクトリ作成は行いません）。"""
        workspace_id = f"{provider_name}_{content_id}"
        return self.workspace_dir / workspace_id

    def persist_metadata(
        self,
        workspace: Workspace,
        metadata: UnifiedContentManifest,
        manifest: WorkspaceManifest,
    ):
        """メタデータ(UCM)とマニフェストをワークスペースに永続化します。"""
        # manifest.jsonの保存
        try:
            with open(workspace.manifest_path, "w", encoding="utf-8") as f:
                json.dump(asdict(manifest), f, ensure_ascii=False, indent=2)
            logger.debug(f"'{MANIFEST_FILE_NAME}' の保存が完了しました。")
        except IOError as e:
            logger.bind(error=str(e)).error(
                f"'{MANIFEST_FILE_NAME}' の保存に失敗しました。"
            )

        # detail.jsonの保存 (UCMを保存)
        try:
            # by_alias=True で @context などのエイリアスが正しく出力される
            metadata_dict = metadata.model_dump(mode="json", by_alias=True)
            detail_path = workspace.source_path / DETAIL_FILE_NAME
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            logger.debug(f"'{DETAIL_FILE_NAME}' の保存が完了しました。")
        except IOError as e:
            logger.bind(error=str(e)).error(
                f"'{DETAIL_FILE_NAME}' の保存に失敗しました。"
            )
