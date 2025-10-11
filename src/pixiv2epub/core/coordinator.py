# FILE: src/pixiv2epub/core/coordinator.py
import shutil
from pathlib import Path
from typing import Any, Dict, List, Type

from loguru import logger

from ..builders.base import BaseBuilder
from ..builders.epub.builder import EpubBuilder
from ..models.workspace import Workspace
from ..providers.base import BaseProvider
from ..providers.pixiv.provider import PixivProvider
from .settings import Settings

AVAILABLE_PROVIDERS: Dict[str, Type[BaseProvider]] = {"pixiv": PixivProvider}
AVAILABLE_BUILDERS: Dict[str, Type[BaseBuilder]] = {"epub": EpubBuilder}


class Coordinator:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _get_provider(self, provider_name: str) -> BaseProvider:
        provider_class = AVAILABLE_PROVIDERS.get(provider_name)
        if not provider_class:
            raise ValueError(f"不明なプロバイダです: {provider_name}")
        return provider_class(self.settings)

    def _get_builder(self, builder_name: str, workspace: Workspace) -> BaseBuilder:
        builder_class = AVAILABLE_BUILDERS.get(builder_name)
        if not builder_class:
            raise ValueError(f"不明なビルダーです: {builder_name}")
        return builder_class(workspace=workspace, settings=self.settings)

    def _is_cleanup_enabled(self) -> bool:
        """クリーンアップが有効かどうかを判定する。"""
        return self.settings.builder.cleanup_after_build

    def _handle_cleanup(self, workspace: Workspace):
        """中間ファイル（ワークスペース）を削除する。"""
        if self._is_cleanup_enabled():
            try:
                logger.info(
                    f"ワークスペースをクリーンアップします: {workspace.root_path}"
                )
                shutil.rmtree(workspace.root_path)
            except OSError as e:
                logger.error(f"ワークスペースのクリーンアップに失敗しました: {e}")

    def download_and_build_novel(
        self,
        provider_name: str,
        builder_name: str,
        novel_id: Any,
    ) -> Path:
        logger.info(f"小説ID: {novel_id} の処理を開始します...")
        provider = self._get_provider(provider_name)
        workspace = provider.get_novel(novel_id)

        builder = self._get_builder(builder_name, workspace)
        output_path = builder.build()

        self._handle_cleanup(workspace)

        logger.info(f"処理が正常に完了しました: {output_path}")
        return output_path

    def download_and_build_series(
        self,
        provider_name: str,
        builder_name: str,
        series_id: Any,
    ) -> List[Path]:
        logger.info(f"シリーズID: {series_id} の処理を開始します...")
        provider = self._get_provider(provider_name)
        workspaces = provider.get_series(series_id)

        output_paths = []
        for workspace in workspaces:
            try:
                builder = self._get_builder(builder_name, workspace)
                output_path = builder.build()
                output_paths.append(output_path)
                self._handle_cleanup(workspace)
            except Exception as e:
                logger.error(
                    f"ワークスペース {workspace.id} のビルドに失敗しました: {e}",
                    exc_info=True,
                )
                self._handle_cleanup(workspace)

        logger.info(f"シリーズ処理完了。{len(output_paths)}/{len(workspaces)}件成功。")
        return output_paths

    def download_and_build_user_novels(
        self,
        provider_name: str,
        builder_name: str,
        user_id: Any,
    ) -> List[Path]:
        logger.info(f"ユーザーID: {user_id} の全作品の処理を開始します...")
        provider = self._get_provider(provider_name)
        workspaces = provider.get_user_novels(user_id)

        output_paths = []
        total = len(workspaces)
        logger.info(f"合計 {total} 件の作品をビルドします。")

        for i, workspace in enumerate(workspaces, 1):
            try:
                logger.info(f"--- Processing {i}/{total}: Workspace {workspace.id} ---")
                builder = self._get_builder(builder_name, workspace)
                output_path = builder.build()
                output_paths.append(output_path)
                self._handle_cleanup(workspace)
            except Exception as e:
                logger.error(
                    f"ワークスペース {workspace.id} のビルドに失敗しました: {e}",
                    exc_info=True,
                )
                self._handle_cleanup(workspace)

        logger.info(f"ユーザー作品処理完了。{len(output_paths)}/{total}件成功。")
        return output_paths
