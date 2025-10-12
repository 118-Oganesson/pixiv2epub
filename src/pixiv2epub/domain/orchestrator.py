# FILE: src/pixiv2epub/domain/orchestrator.py
import shutil
from pathlib import Path
from typing import Any, List, Type

from loguru import logger

from ..infrastructure.builders.base import BaseBuilder
from ..infrastructure.providers.base import IProvider
from ..models.workspace import Workspace
from ..shared.settings import Settings


class DownloadBuildOrchestrator:
    """
    データ取得(Provider)と成果物生成(Builder)のワークフローを調整する責務を持つ。
    """

    def __init__(
        self,
        provider: IProvider,
        builder_class: Type[BaseBuilder],
        settings: Settings,
    ):
        self.provider = provider
        self.builder_class = builder_class
        self.settings = settings

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

    def process_novel(self, novel_id: Any) -> Path:
        """単一の小説をダウンロードし、ビルドします。"""
        logger.info(f"小説ID: {novel_id} の処理を開始します...")
        workspace = self.provider.get_novel(novel_id)

        # Workspaceが確定した後にBuilderをインスタンス化する
        builder = self.builder_class(workspace=workspace, settings=self.settings)
        output_path = builder.build()

        self._handle_cleanup(workspace)

        logger.info(f"処理が正常に完了しました: {output_path}")
        return output_path

    def process_series(self, series_id: Any) -> List[Path]:
        """シリーズ作品をダウンロードし、ビルドします。"""
        logger.info(f"シリーズID: {series_id} の処理を開始します...")
        workspaces = self.provider.get_series(series_id)

        output_paths = []
        for workspace in workspaces:
            try:
                builder = self.builder_class(
                    workspace=workspace, settings=self.settings
                )
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

    def process_user_novels(self, user_id: Any) -> List[Path]:
        """ユーザーの全作品をダウンロードし、ビルドします。"""
        logger.info(f"ユーザーID: {user_id} の全作品の処理を開始します...")
        workspaces = self.provider.get_user_novels(user_id)

        output_paths = []
        total = len(workspaces)
        logger.info(f"合計 {total} 件の作品をビルドします。")

        for i, workspace in enumerate(workspaces, 1):
            try:
                logger.info(f"--- Processing {i}/{total}: Workspace {workspace.id} ---")
                builder = self.builder_class(
                    workspace=workspace, settings=self.settings
                )
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
