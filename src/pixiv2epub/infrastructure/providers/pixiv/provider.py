# FILE: src/pixiv2epub/infrastructure/providers/pixiv/provider.py
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from loguru import logger
from pixivpy3 import PixivError
from pydantic import ValidationError
from pybreaker import CircuitBreaker

from ....domain.interfaces import (
    ICreatorProvider,
    IMultiWorkProvider,
    IWorkProvider,
    IWorkspaceRepository,
)
from ....models.pixiv import NovelSeriesApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import ApiError, DataProcessingError
from ....shared.settings import Settings
from ..base_provider import BaseProvider
from .client import PixivApiClient
from .content_processor import PixivContentProcessor
from .fetcher import PixivFetcher


class PixivProvider(BaseProvider, IWorkProvider, IMultiWorkProvider, ICreatorProvider):
    """
    Pixivから小説データを取得するためのプロバイダ。
    Fetcher, Processor, Repository に処理を委譲するオーケストレーターとして機能します。
    """

    def __init__(
        self,
        settings: Settings,
        api_client: PixivApiClient,
        breaker: CircuitBreaker,
        fetcher: PixivFetcher,
        processor: PixivContentProcessor,
        repository: IWorkspaceRepository,
    ):
        """
        Args:
            settings (Settings): アプリケーション設定。
            api_client (PixivApiClient): 認証済みのPixiv APIクライアント。
            breaker (CircuitBreaker): 共有サーキットブレーカーインスタンス。
            fetcher (PixivFetcher): データ取得担当。
            processor (PixivContentProcessor): データ処理担当。
            repository (IWorkspaceRepository): ワークスペース永続化担当。
        """
        super().__init__(settings, breaker)
        self.api_client = api_client
        self.fetcher = fetcher
        self.processor = processor
        self.repository = repository

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def get_work(self, work_id: Any) -> Optional[Workspace]:
        logger.info("小説の処理を開始")
        workspace = self.repository.setup_workspace(work_id, self.get_provider_name())

        try:
            # 1. データの取得
            raw_webview_data, raw_detail_data = self.fetcher.fetch_novel_data(work_id)

            # 2. 更新のチェック
            update_required, new_hash = self.processor.check_for_updates(
                workspace, raw_webview_data
            )
            if not update_required:
                logger.bind(workspace_id=workspace.id).info(
                    "コンテンツに変更なし、スキップします。"
                )
                return None

            # 3. コンテンツの処理とワークスペースへの保存
            metadata = self.processor.process_and_populate_workspace(
                workspace, raw_webview_data, raw_detail_data
            )

            # 4. メタデータとマニフェストの永続化
            manifest = WorkspaceManifest(
                provider_name=self.get_provider_name(),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                source_metadata={"novel_id": work_id},
                content_hash=new_hash,
            )
            self.repository.persist_metadata(workspace, metadata, manifest)

            logger.bind(
                title=metadata.title, workspace_path=str(workspace.root_path)
            ).info("小説データ取得完了")
            return workspace

        except (PixivError, ApiError) as e:
            raise ApiError(
                f"小説ID {work_id} のデータ取得に失敗: {e}",
                self.get_provider_name(),
            ) from e
        except (ValidationError, KeyError, TypeError) as e:
            raise DataProcessingError(
                f"小説ID {work_id} のデータ解析に失敗: {e}",
                self.get_provider_name(),
            ) from e

    def get_multiple_works(self, series_id: Any) -> List[Workspace]:
        logger.info("シリーズの処理を開始")
        try:
            series_data = self.get_series_info(series_id)
            novel_ids = [novel.id for novel in series_data.novels]

            if not novel_ids:
                logger.info("ダウンロード対象が見つからず処理を終了します。")
                return []

            downloaded_workspaces = []
            total = len(novel_ids)
            logger.bind(total_novels=total).info("シリーズ内の小説ダウンロードを開始")

            for i, novel_id in enumerate(novel_ids, 1):
                log = logger.bind(current=i, total=total, novel_id=novel_id)
                log.info("--- 小説を処理中 ---")
                try:
                    workspace = self.get_work(novel_id)
                    if workspace:
                        downloaded_workspaces.append(workspace)
                except Exception as e:
                    log.bind(error=str(e)).error(
                        "小説のダウンロードに失敗しました。", exc_info=True
                    )

            logger.bind(series_title=series_data.novel_series_detail.title).info(
                "シリーズのダウンロード完了"
            )
            return downloaded_workspaces
        except Exception as e:
            raise ApiError(
                f"シリーズID {series_id} の処理中にエラーが発生: {e}",
                self.get_provider_name(),
            ) from e

    def get_series_info(self, series_id: Any) -> NovelSeriesApiResponse:
        try:
            series_data_dict = self.api_client.novel_series(series_id)
            return NovelSeriesApiResponse.model_validate(series_data_dict)
        except PixivError as e:
            raise ApiError(
                f"シリーズID {series_id} のメタデータ取得に失敗: {e}",
                self.get_provider_name(),
            ) from e

    def get_creator_works(self, user_id: Any) -> List[Workspace]:
        logger.info("ユーザーの全作品の処理を開始")
        try:
            single_ids, series_ids = self._fetch_all_user_novel_ids(user_id)
            logger.bind(
                series_count=len(series_ids), single_work_count=len(single_ids)
            ).info("ユーザー作品の取得結果")

            downloaded_workspaces = []
            if series_ids:
                logger.info("--- シリーズ作品の処理を開始 ---")
                for i, s_id in enumerate(series_ids, 1):
                    log = logger.bind(current_series=i, total_series=len(series_ids))
                    log.info("--- シリーズを処理中 ---")
                    try:
                        workspaces = self.get_multiple_works(s_id)
                        downloaded_workspaces.extend(workspaces)
                    except Exception as e:
                        log.bind(series_id=s_id, error=str(e)).error(
                            "シリーズの処理中にエラーが発生しました。",
                            exc_info=True,
                        )

            if single_ids:
                logger.info("--- 単独作品の処理を開始 ---")
                for i, n_id in enumerate(single_ids, 1):
                    log = logger.bind(current_work=i, total_works=len(single_ids))
                    log.info("--- 単独作品を処理中 ---")
                    try:
                        workspace = self.get_work(n_id)
                        if workspace:
                            downloaded_workspaces.append(workspace)
                    except Exception as e:
                        log.bind(novel_id=n_id, error=str(e)).error(
                            "小説の処理中にエラーが発生しました。", exc_info=True
                        )
            return downloaded_workspaces
        except Exception as e:
            raise ApiError(
                f"ユーザーID {user_id} の作品処理中にエラーが発生: {e}",
                self.get_provider_name(),
            ) from e

    def _fetch_all_user_novel_ids(self, user_id: int) -> Tuple[List[int], List[int]]:
        """指定されたユーザーの全小説IDを取得し、単独作品とシリーズ作品IDに分離します。"""
        single_ids, series_ids = [], set()
        next_url = None
        while True:
            res = self.api_client.user_novels(user_id, next_url)
            for novel in res.get("novels", []):
                if novel.get("series") and novel["series"].get("id"):
                    series_ids.add(novel["series"]["id"])
                else:
                    single_ids.append(novel["id"])
            if not (next_url := res.get("next_url")):
                break
        return single_ids, list(series_ids)
