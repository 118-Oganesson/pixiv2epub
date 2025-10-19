# FILE: src/pixiv2epub/infrastructure/providers/fanbox/provider.py
from typing import Any, List

from loguru import logger
from pybreaker import CircuitBreaker

from ....domain.interfaces import (
    ICreatorProvider,
    IWorkProvider,
    IWorkspaceRepository,
)
from ....models.workspace import Workspace
from ....shared.settings import Settings
from ..base_provider import BaseProvider
from .client import FanboxApiClient
from .content_processor import FanboxContentProcessor
from .fetcher import FanboxFetcher


class FanboxProvider(BaseProvider, IWorkProvider, ICreatorProvider):
    """
    Fanboxから投稿データを取得するためのプロバイダ。
    共通のワークフローはBaseProviderに委譲し、自身は依存関係の構築と
    作者作品取得など、Fanbox固有のロジックに責任を持つ。
    """

    def __init__(
        self,
        settings: Settings,
        api_client: FanboxApiClient,
        breaker: CircuitBreaker,
        repository: IWorkspaceRepository,
        fetcher: FanboxFetcher,
        processor: FanboxContentProcessor,
    ):
        """
        Args:
            settings (Settings): アプリケーション設定。
            api_client (FanboxApiClient): 認証済みのFanbox APIクライアント。
            breaker (CircuitBreaker): 共有サーキットブレーカーインスタンス。
            repository (IWorkspaceRepository): ワークスペース永続化担当。
            fetcher (FanboxFetcher): データ取得担当。
            processor (FanboxContentProcessor): データ処理担当。
        """
        super().__init__(
            settings=settings,
            breaker=breaker,
            fetcher=fetcher,
            processor=processor,
            repository=repository,
        )
        self.api_client = api_client

    @classmethod
    def get_provider_name(cls) -> str:
        return "fanbox"

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
