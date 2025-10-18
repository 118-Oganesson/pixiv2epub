# FILE: src/pixiv2epub/domain/orchestrator.py
import shutil
from pathlib import Path
from typing import Any, List, Optional, Callable

from loguru import logger

from ..domain.interfaces import (
    IBuilder,
    ICreatorProvider,
    IMultiWorkProvider,
    IProvider,
    IProviderFactory,
    IWorkProvider,
)
from ..models.workspace import Workspace
from ..shared.enums import ContentType
from ..shared.exceptions import BuildError, ContentNotFoundError, ProviderError
from ..shared.settings import Settings
from ..utils.url_parser import parse_content_identifier


class DownloadBuildOrchestrator:
    """
    データ取得(Provider)と成果物生成(Builder)のワークフローを調整する責務を持つ。
    アプリケーションの主要なユースケースを実装します。
    """

    def __init__(
        self,
        builder: IBuilder,
        settings: Settings,
        provider_factory: IProviderFactory,
    ):
        self.builder = builder
        self.settings = settings
        self.provider_factory = provider_factory

    def run_from_input(self, input_str: str, download_only: bool = False) -> List[Path]:
        """
        単一の入力（URLやID）から適切な処理を判断し、実行する。
        """
        provider_enum, content_type, target_id = parse_content_identifier(input_str)
        provider = self.provider_factory.create(provider_enum)

        with logger.contextualize(
            provider=provider_enum.name,
            content_type=content_type.name,
            target_id=str(target_id),
        ):
            if download_only:
                logger.info("ダウンロード処理のみを開始")
                workspaces = self._download(provider, content_type, target_id)
                logger.bind(download_count=len(workspaces)).success(
                    "ダウンロード処理が完了しました。"
                )
                return []  # ダウンロードのみなので出力パスは返さない
            else:
                logger.info("ダウンロードとビルド処理を開始")
                if content_type == ContentType.WORK:
                    path = self._process_work(provider, target_id)
                    return [path] if path else []
                elif content_type == ContentType.SERIES:
                    return self._process_series(provider, target_id)
                elif content_type == ContentType.CREATOR:
                    return self._process_creator(provider, target_id)
                else:
                    logger.error(f"未対応のコンテンツタイプです: {content_type}")
                    return []

    def _is_cleanup_enabled(self) -> bool:
        """クリーンアップが有効かどうかを判定する。"""
        return self.settings.builder.cleanup_after_build

    def _handle_cleanup(self, workspace: Workspace):
        """中間ファイル（ワークスペース）を削除する。"""
        if self._is_cleanup_enabled():
            log = logger.bind(workspace_path=str(workspace.root_path))
            try:
                log.info("ワークスペースのクリーンアップを開始")
                shutil.rmtree(workspace.root_path)
            except OSError as e:
                log.bind(error=str(e)).error("ワークスペースのクリーンアップ失敗")

    def _process_work(self, provider: IProvider, work_id: Any) -> Optional[Path]:
        """単一の作品をダウンロードし、ビルドします。"""
        workspace: Optional[Workspace] = None
        try:
            logger.info("単一作品の処理を開始")
            if not isinstance(provider, IWorkProvider):
                raise TypeError(
                    "現在のプロバイダは単一作品の取得をサポートしていません。"
                )

            workspace = provider.get_work(work_id)

            if workspace is None:
                logger.info("コンテンツ更新なし、ビルドをスキップ")
                return None

            output_path = self.builder.build(workspace)

            logger.bind(output_path=str(output_path)).success("単一作品の処理完了")
            return output_path
        finally:
            if workspace:
                self._handle_cleanup(workspace)

    def _process_collection(
        self,
        collection_id: Any,
        fetch_func: Callable[[Any], List[Workspace]],
        collection_type: str,
    ) -> List[Path]:
        """作品群を処理するための共通ロジック。"""
        logger.info(f"{collection_type} の処理を開始")

        workspaces: List[Workspace] = fetch_func(collection_id)

        if not workspaces:
            logger.warning("処理対象の作品が見つかりませんでした。")
            return []

        output_paths: List[Path] = []
        total = len(workspaces)
        logger.bind(total_works=total).info("作品群のビルドを開始")

        for i, workspace in enumerate(workspaces, 1):
            try:
                with logger.contextualize(workspace_id=workspace.id):
                    logger.bind(current_work=i, total_works=total).info(
                        "個別作品の処理を開始"
                    )
                    output_path = self.builder.build(workspace)
                    output_paths.append(output_path)
            except ContentNotFoundError as e:
                logger.bind(reason=str(e)).warning("コンテンツが見つからずスキップ")
                continue
            except (BuildError, ProviderError) as e:
                logger.bind(workspace_id=workspace.id, error=str(e)).error(
                    "ワークスペースの処理失敗",
                    exc_info=self.settings.log_level == "DEBUG",
                )
            except Exception:
                logger.bind(workspace_id=workspace.id).error(
                    "ワークスペース処理中に予期せぬエラー発生",
                    exc_info=True,
                )
            finally:
                if workspace:
                    self._handle_cleanup(workspace)

        logger.bind(success_count=len(output_paths), total_works=total).success(
            f"{collection_type} の処理完了"
        )
        return output_paths

    def _process_series(self, provider: IProvider, series_id: Any) -> List[Path]:
        """シリーズ作品をダウンロードし、ビルドします。"""
        if not isinstance(provider, IMultiWorkProvider):
            raise TypeError("現在のプロバイダはシリーズの取得をサポートしていません。")
        return self._process_collection(
            series_id, provider.get_multiple_works, "Series"
        )

    def _process_creator(self, provider: IProvider, creator_id: Any) -> List[Path]:
        """クリエイターの全作品をダウンロードし、ビルドします。"""
        if not isinstance(provider, ICreatorProvider):
            raise TypeError(
                "現在のプロバイダはクリエイター作品の取得をサポートしていません。"
            )
        return self._process_collection(
            creator_id, provider.get_creator_works, "Creator"
        )

    def _download(
        self, provider: IProvider, content_type: ContentType, target_id: Any
    ) -> List[Workspace]:
        """ダウンロード処理のみを実行します。"""
        workspaces: List[Workspace] = []
        if content_type == ContentType.WORK and isinstance(provider, IWorkProvider):
            workspace = provider.get_work(target_id)
            if workspace:
                workspaces.append(workspace)
        elif content_type == ContentType.SERIES and isinstance(
            provider, IMultiWorkProvider
        ):
            workspaces = provider.get_multiple_works(target_id)
        elif content_type == ContentType.CREATOR and isinstance(
            provider, ICreatorProvider
        ):
            workspaces = provider.get_creator_works(target_id)
        else:
            raise TypeError(
                f"現在のProviderは {content_type.name} のダウンロードをサポートしていません。"
            )
        return workspaces
