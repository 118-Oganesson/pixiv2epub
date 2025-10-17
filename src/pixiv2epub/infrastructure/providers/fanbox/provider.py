# FILE: src/pixiv2epub/infrastructure/providers/fanbox/provider.py
import shutil
from datetime import datetime, timezone
from typing import Any, List, Optional

from loguru import logger
from pydantic import ValidationError
from requests.exceptions import RequestException

from ....domain.interfaces import ICreatorProvider, IWorkProvider
from ....models.fanbox import FanboxPostApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import ApiError, DataProcessingError
from ....shared.settings import Settings
from ...strategies.mappers import FanboxMetadataMapper
from ...strategies.parsers import FanboxBlockParser
from ...strategies.update_checkers import TimestampUpdateStrategy
from ..base_provider import BaseProvider
from .client import FanboxApiClient
from .downloader import FanboxImageDownloader


class FanboxProvider(BaseProvider, IWorkProvider, ICreatorProvider):
    """Fanboxから投稿データを取得し、ワークスペースを生成するためのプロバイダ。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_client = FanboxApiClient(
            breaker=self.breaker,
            provider_name=self.get_provider_name(),
            sessid=settings.providers.fanbox.sessid,
            api_delay=settings.downloader.api_delay,
            api_retries=settings.downloader.api_retries,
        )
        # Fanbox用の戦略オブジェクトをインスタンス化
        self.update_checker = TimestampUpdateStrategy(timestamp_key="updatedDatetime")
        self.parser = FanboxBlockParser()
        self.mapper = FanboxMetadataMapper()

    @classmethod
    def get_provider_name(cls) -> str:
        return "fanbox"

    def _save_page(self, workspace: Workspace, parsed_html: str):
        filename = workspace.source_path / "page-1.xhtml"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(parsed_html)
            logger.debug("1ページの保存が完了しました。")
        except IOError as e:
            logger.bind(error=str(e)).error("ページの保存に失敗しました。")

    def get_work(self, work_id: Any) -> Optional[Workspace]:
        with logger.contextualize(provider=self.get_provider_name(), work_id=work_id):
            logger.info("Fanbox投稿の処理を開始します。")
            workspace = self._setup_workspace(work_id)

            try:
                # --- API呼び出しと画像ダウンロード ---
                post_data_dict = self.api_client.post_info(work_id)
                post_data_body = post_data_dict.get("body", {})

                update_required, new_timestamp = self.update_checker.is_update_required(
                    workspace, post_data_body
                )

                if not update_required:
                    logger.bind(workspace_id=workspace.id).info(
                        "コンテンツに変更はありません。処理をスキップします。"
                    )
                    return None

                logger.info(
                    "コンテンツの更新を検出しました。ダウンロードを続行します。"
                )
                if workspace.source_path.exists():
                    shutil.rmtree(workspace.source_path)
                workspace.source_path.mkdir(parents=True, exist_ok=True)

                downloader = FanboxImageDownloader(
                    api_client=self.api_client,
                    image_dir=workspace.assets_path / "images",
                    overwrite=self.settings.downloader.overwrite_existing_images,
                )

            except (RequestException, ApiError) as e:
                raise ApiError(
                    f"投稿ID {work_id} のデータ取得に失敗: {e}",
                    self.get_provider_name(),
                ) from e

            try:
                # --- ダウンロード後のデータ処理 ---
                post_data = FanboxPostApiResponse.model_validate(post_data_dict).body

                cover_path = downloader.download_cover(post_data)
                image_paths = downloader.download_embedded_images(post_data)

                parsed_html = self.parser.parse(post_data.body, image_paths)
                self._save_page(workspace, parsed_html)

                metadata = self.mapper.map_to_metadata(
                    workspace=workspace, cover_path=cover_path, post_data=post_data
                )

                manifest = WorkspaceManifest(
                    provider_name=self.get_provider_name(),
                    created_at_utc=datetime.now(timezone.utc).isoformat(),
                    source_metadata={
                        "post_id": work_id,
                        "creator_id": post_data.creator_id,
                    },
                    content_hash=new_timestamp,
                )
                self._persist_metadata(workspace, metadata, manifest)

                logger.bind(
                    title=post_data.title, workspace_path=str(workspace.root_path)
                ).info("投稿のデータ取得が完了しました。")
                return workspace

            except (ValidationError, KeyError, TypeError) as e:
                raise DataProcessingError(
                    f"投稿ID {work_id} のデータ解析に失敗: {e}",
                    self.get_provider_name(),
                ) from e

    def _fetch_all_creator_post_ids(self, creator_id: Any) -> List[str]:
        """ページネーションを利用して、クリエイターの全投稿IDを取得する。"""
        logger.bind(creator_id=creator_id).info(
            "クリエイターの全投稿IDの取得を開始します。"
        )
        post_ids = []

        try:
            # 1. まず、全ての投稿ページのURLリストを取得する
            paginate_response = self.api_client.post_paginate_creator(creator_id)
            page_urls = paginate_response.get("body")

            if not isinstance(page_urls, list):
                logger.error(
                    "投稿ページの一覧が取得できませんでした。APIのレスポンスが予期しない形式です。"
                )
                return []

            total_pages = len(page_urls)
            logger.bind(total_pages=total_pages).info(
                "投稿リストのページ数を取得しました。"
            )

            # 2. 取得した各ページのURLを辿り、投稿リストを取得する
            for i, page_url in enumerate(page_urls, 1):
                log = logger.bind(
                    current_page=i, total_pages=total_pages, page_url=page_url
                )
                log.debug("投稿リストを取得中...")
                try:
                    list_response = self.api_client.post_list_creator(page_url)
                    post_items = list_response.get("body", [])
                    if isinstance(post_items, list):
                        for item in post_items:
                            if isinstance(item, dict) and "id" in item:
                                post_ids.append(item["id"])
                    else:
                        log.warning("投稿リストの形式が不正です。スキップします。")

                except Exception as e:
                    log.bind(error=str(e)).error(
                        "投稿リスト取得中にエラーが発生しました。",
                        exc_info=self.settings.log_level == "DEBUG",
                    )
                    continue

        except Exception as e:
            logger.bind(error=str(e)).error(
                "投稿ページ一覧の取得中に致命的なエラーが発生しました。",
                exc_info=self.settings.log_level == "DEBUG",
            )
            return []

        logger.bind(count=len(post_ids)).info("投稿IDの取得が完了しました。")
        return post_ids

    def get_creator_works(self, creator_id: Any) -> List[Workspace]:
        """クリエイターの全投稿をダウンロードし、Workspaceのリストを返す。"""
        with logger.contextualize(
            provider=self.get_provider_name(), creator_id=creator_id
        ):
            post_ids = self._fetch_all_creator_post_ids(creator_id)
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
