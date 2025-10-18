# FILE: src/pixiv2epub/infrastructure/providers/fanbox/provider.py
from datetime import datetime, timezone
from typing import Any, List, Optional

from loguru import logger
from pybreaker import CircuitBreaker
from requests.exceptions import RequestException

from ....domain.interfaces import (
    ICreatorProvider,
    IFanboxImageDownloader,
    IWorkProvider,
    IWorkspaceRepository,
)
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import ApiError
from ....shared.settings import Settings
from ..base_provider import BaseProvider
from .client import FanboxApiClient
from .content_processor import FanboxContentProcessor
from .fetcher import FanboxFetcher


class FanboxProvider(BaseProvider, IWorkProvider, ICreatorProvider):
    """
    Fanboxから投稿データを取得するためのプロバイダ。
    Fetcher, Processor, Repository に処理を委譲するオーケストレーターとして機能します。
    """

    def __init__(
        self,
        settings: Settings,
        api_client: FanboxApiClient,
        downloader: IFanboxImageDownloader,
        breaker: CircuitBreaker,
        repository: IWorkspaceRepository,
        fetcher: FanboxFetcher,
        processor: FanboxContentProcessor,
    ):
        """
        Args:
            settings (Settings): アプリケーション設定。
            api_client (FanboxApiClient): 認証済みのFanbox APIクライアント。
            downloader (IFanboxImageDownloader): Fanbox画像ダウンロード用インターフェース。
            breaker (CircuitBreaker): 共有サーキットブレーカーインスタンス。
            repository (IWorkspaceRepository): ワークスペース永続化担当。
            fetcher (FanboxFetcher): データ取得担当。
            processor (FanboxContentProcessor): データ処理担当。
        """
        super().__init__(settings, breaker)
        self.api_client = api_client
        self.downloader = downloader
        self.repository = repository
        self.fetcher = fetcher
        self.processor = processor

    @classmethod
    def get_provider_name(cls) -> str:
        return "fanbox"

    def get_work(self, content_id: Any) -> Optional[Workspace]:
        logger.info("Fanbox投稿の処理を開始")
        workspace = self.repository.setup_workspace(
            content_id, self.get_provider_name()
        )

        try:
            # 1. データの取得
            post_data_dict = self.fetcher.fetch_post_data(content_id)

            # 2. 更新のチェック
            update_required, new_timestamp = self.processor.check_for_updates(
                workspace, post_data_dict
            )
            if not update_required:
                logger.bind(workspace_id=workspace.id).info(
                    "コンテンツに変更なし、スキップします。"
                )
                return None

            # 3. コンテンツの処理とワークスペースへの保存
            metadata = self.processor.process_and_populate_workspace(
                workspace, post_data_dict
            )

            # 4. メタデータとマニフェストの永続化
            manifest = WorkspaceManifest(
                provider_name=self.get_provider_name(),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                source_metadata={
                    "post_id": content_id,
                    "creator_id": metadata.identifier.creator_id,
                },
                content_hash=new_timestamp,
            )
            self.repository.persist_metadata(workspace, metadata, manifest)

            logger.bind(
                title=metadata.title, workspace_path=str(workspace.root_path)
            ).info("投稿データ取得完了")
            return workspace

        except (RequestException, ApiError) as e:
            raise ApiError(
                f"投稿ID {content_id} のデータ取得に失敗: {e}",
                self.get_provider_name(),
            ) from e

    def _fetch_all_creator_post_ids(self, creator_id: Any) -> List[str]:
        """ページネーションを利用して、クリエイターの全投稿IDを取得する。"""
        log = logger.bind(creator_id=creator_id)
        log.info("クリエイターの全投稿IDの取得を開始")
        post_ids = []

        try:
            # 1. まず、全ての投稿ページのURLリストを取得する
            paginate_response = self.api_client.post_paginate_creator(creator_id)
            page_urls = paginate_response.get("body")

            if not isinstance(page_urls, list):
                log.error(
                    "投稿ページの一覧が取得できませんでした。APIのレスポンスが予期しない形式です。"
                )
                return []

            total_pages = len(page_urls)
            log.bind(total_pages=total_pages).info(
                "投稿リストのページ数を取得しました。"
            )

            # 2. 取得した各ページのURLを辿り、投稿リストを取得する
            for i, page_url in enumerate(page_urls, 1):
                page_log = log.bind(
                    current_page=i, total_pages=total_pages, page_url=page_url
                )
                page_log.debug("投稿リストを取得中...")
                try:
                    list_response = self.api_client.post_list_creator(page_url)
                    post_items = list_response.get("body", [])
                    if isinstance(post_items, list):
                        for item in post_items:
                            if isinstance(item, dict) and "id" in item:
                                post_ids.append(item["id"])
                    else:
                        page_log.warning("投稿リストの形式が不正です。スキップします。")

                except Exception as e:
                    page_log.bind(error=str(e)).error(
                        "投稿リスト取得中にエラーが発生しました。",
                        exc_info=self.settings.log_level == "DEBUG",
                    )
                    continue

        except Exception as e:
            log.bind(error=str(e)).error(
                "投稿ページ一覧の取得中に致命的なエラーが発生しました。",
                exc_info=self.settings.log_level == "DEBUG",
            )
            return []

        log.bind(count=len(post_ids)).info("投稿IDの取得が完了しました。")
        return post_ids

    def get_creator_works(self, collection_id: Any) -> List[Workspace]:
        """クリエイターの全投稿をダウンロードし、Workspaceのリストを返す。"""
        post_ids = self._fetch_all_creator_post_ids(collection_id)
        workspaces = []
        total = len(post_ids)
        for i, post_id in enumerate(post_ids, 1):
            log = logger.bind(current=i, total=total, post_id=post_id)
            log.info("--- 投稿を処理中 ---")
            try:
                workspace = self.get_work(post_id)
                if workspace:
                    workspaces.append(workspace)
            except Exception as e:
                log.bind(error=str(e)).error(
                    "投稿の処理に失敗しました。",
                    exc_info=self.settings.log_level == "DEBUG",
                )
        return workspaces
