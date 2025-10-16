# FILE: src/pixiv2epub/domain/orchestrator.py
import shutil
from pathlib import Path
from typing import Any, List, Optional

from loguru import logger

from ..infrastructure.providers.base import (
    ICreatorProvider,
    IMultiWorkProvider,
    IProvider,
    IWorkProvider,
)
from ..models.workspace import Workspace
from ..shared.exceptions import BuildError, ContentNotFoundError, ProviderError
from ..shared.settings import Settings
from .interfaces import IBuilder


class DownloadBuildOrchestrator:
    """
    データ取得(Provider)と成果物生成(Builder)のワークフローを調整する責務を持つ。
    """

    def __init__(
        self,
        provider: IProvider,
        builder: IBuilder,
        settings: Settings,
    ):
        self.provider = provider
        self.builder = builder
        self.settings = settings

    def _is_cleanup_enabled(self) -> bool:
        """クリーンアップが有効かどうかを判定する。"""
        return self.settings.builder.cleanup_after_build

    def _handle_cleanup(self, workspace: Workspace):
        """中間ファイル（ワークスペース）を削除する。"""
        if self._is_cleanup_enabled():
            try:
                logger.info(
                    "ワークスペースをクリーンアップします: {}", workspace.root_path
                )
                shutil.rmtree(workspace.root_path)
            except OSError as e:
                logger.error("ワークスペースのクリーンアップに失敗しました: {}", e)

    def process_work(self, work_id: Any) -> Optional[Path]:
        """単一の作品をダウンロードし、ビルドします。"""
        workspace: Optional[Workspace] = None
        with logger.contextualize(
            provider=self.provider.get_provider_name(), work_id=work_id
        ):
            try:
                logger.info("作品の処理を開始します...")
                if not isinstance(self.provider, IWorkProvider):
                    raise TypeError(
                        "現在のProviderは単一作品の取得をサポートしていません。"
                    )

                workspace = self.provider.get_work(work_id)

                if workspace is None:
                    logger.info("更新が不要なため、ビルド処理をスキップしました。")
                    return None

                output_path = self.builder.build(workspace)

                logger.success("処理が正常に完了しました: {}", output_path)
                return output_path
            finally:
                if workspace:
                    self._handle_cleanup(workspace)

    def process_collection(self, collection_id: Any, is_series: bool) -> List[Path]:
        """
        作品群（シリーズやクリエイター作品）をダウンロードし、ビルドします。
        """
        log_prefix = "シリーズ" if is_series else "クリエイター"
        with logger.contextualize(
            provider=self.provider.get_provider_name(),
            collection_id=collection_id,
            is_series=is_series,
        ):
            logger.info("{}の処理を開始します...", log_prefix)

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
            logger.info("合計 {} 件の作品をビルドします。", total)

            for i, workspace in enumerate(workspaces, 1):
                try:
                    with logger.contextualize(workspace_id=workspace.id):
                        logger.info("--- Processing {}/{} ---", i, total)
                        output_path = self.builder.build(workspace)
                        output_paths.append(output_path)
                except ContentNotFoundError as e:
                    logger.warning(
                        "コンテンツが見つからなかったためスキップします: {}", e
                    )
                    continue
                except (BuildError, ProviderError) as e:
                    logger.error(
                        "ワークスペース {} の処理に失敗しました: {}",
                        workspace.id,
                        e,
                        exc_info=self.settings.log_level == "DEBUG",
                    )
                except Exception:
                    logger.error(
                        "ワークスペース {} の処理中に予期せぬエラーが発生しました。",
                        workspace.id,
                        exc_info=True,
                    )
                finally:
                    self._handle_cleanup(workspace)

            logger.success(
                "{}処理完了。{}/{}件成功。", log_prefix, len(output_paths), total
            )
            return output_paths
