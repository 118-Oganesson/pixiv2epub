# FILE: src/pixiv2epub/domain/orchestrator.py
import shutil
from pathlib import Path
from typing import Any, List, Type

from loguru import logger

from ..infrastructure.builders.base import BaseBuilder
from ..infrastructure.providers.base import (
    ICreatorProvider,
    IMultiWorkProvider,
    IProvider,
    IWorkProvider,
)
from ..models.workspace import Workspace
from ..shared.exceptions import BuildError, ContentNotFoundError, ProviderError
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

    def process_work(self, work_id: Any) -> Path:
        """単一の作品をダウンロードし、ビルドします。"""
        logger.info(f"作品ID: {work_id} の処理を開始します...")
        if not isinstance(self.provider, IWorkProvider):
            raise TypeError("現在のProviderは単一作品の取得をサポートしていません。")

        workspace = self.provider.get_work(work_id)
        builder = self.builder_class(workspace=workspace, settings=self.settings)
        output_path = builder.build()

        self._handle_cleanup(workspace)

        logger.success(f"処理が正常に完了しました: {output_path}")
        return output_path

    def process_collection(self, collection_id: Any, is_series: bool) -> List[Path]:
        """
        作品群（シリーズやクリエイター作品）をダウンロードし、ビルドします。
        """
        log_prefix = "シリーズ" if is_series else "クリエイター"
        logger.info(f"{log_prefix}ID: {collection_id} の処理を開始します...")

        workspaces: List[Workspace] = []
        if is_series and isinstance(self.provider, IMultiWorkProvider):
            workspaces = self.provider.get_multiple_works(collection_id)
        elif not is_series and isinstance(self.provider, ICreatorProvider):
            workspaces = self.provider.get_creator_works(collection_id)
        else:
            raise TypeError(
                f"現在のProviderは{log_prefix}作品の取得をサポートしていません。"
            )

        if not workspaces:
            logger.info("処理対象の作品が見つかりませんでした。")
            return []

        output_paths: List[Path] = []
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
            except ContentNotFoundError as e:
                logger.warning(f"コンテンツが見つからなかったためスキップします: {e}")
                self._handle_cleanup(workspace)
                continue
            except (BuildError, ProviderError) as e:
                logger.error(
                    f"ワークスペース {workspace.id} の処理に失敗しました: {e}",
                    exc_info=self.settings.log_level == "DEBUG",
                )
                self._handle_cleanup(workspace)
            except Exception:
                logger.error(
                    f"ワークスペース {workspace.id} の処理中に予期せぬエラーが発生しました。",
                    exc_info=True,
                )
                self._handle_cleanup(workspace)

        logger.success(f"{log_prefix}処理完了。{len(output_paths)}/{total}件成功。")
        return output_paths
