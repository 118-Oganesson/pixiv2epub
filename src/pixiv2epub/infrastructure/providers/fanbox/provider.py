# FILE: src/pixiv2epub/infrastructure/providers/fanbox/provider.py
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pydantic import ValidationError

from ....domain.interfaces import IProvider, IWorkspaceRepository
from ....models.domain import NovelMetadata
from ....models.fanbox import FanboxPostApiResponse, Post
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.constants import IMAGES_DIR_NAME, MANIFEST_FILE_NAME
from ....shared.enums import ContentType
from ....shared.exceptions import DataProcessingError, ProviderError
from ....shared.settings import Settings
from ...strategies.mappers import FanboxMetadataMapper
from ...strategies.parsers import FanboxBlockParser
from .client import FanboxApiClient
from .downloader import FanboxImageDownloader


class FanboxProvider(IProvider):
    """
    Fanboxから投稿データを取得するための、自己完結した高性能プロバイダ。
    Fetcher, Processor, Downloaderの責務を内部に統合し、
    APIコールを最適化するロジックを実装しています。
    """

    def __init__(
        self,
        settings: Settings,
        api_client: FanboxApiClient,
        repository: IWorkspaceRepository,
    ):
        """
        Args:
            settings (Settings): アプリケーション設定。
            api_client (FanboxApiClient): 認証済みのFanbox APIクライアント。
            repository (IWorkspaceRepository): ワークスペース永続化担当。
        """
        self.settings = settings
        self.api_client = api_client
        self.repository = repository
        # 内部で利用するコンポーネントをインスタンス化
        self._downloader = FanboxImageDownloader(
            api_client=self.api_client,
            overwrite=self.settings.downloader.overwrite_existing_images,
        )
        self._parser = FanboxBlockParser()
        self._mapper = FanboxMetadataMapper()

    @classmethod
    def get_provider_name(cls) -> str:
        return "fanbox"

    def get_works(self, identifier: Any, content_type: ContentType) -> List[Workspace]:
        """
        IProviderインターフェースの統一エントリーポイント。
        コンテンツ種別に応じて適切な内部メソッドに処理を委譲します。
        """
        if content_type == ContentType.WORK:
            workspace = self._get_single_work(str(identifier))
            return [workspace] if workspace else []
        elif content_type == ContentType.CREATOR:
            return self._get_creator_works(str(identifier))
        else:
            raise ProviderError(
                f"Fanbox provider does not support content type: {content_type.name}",
                self.get_provider_name(),
            )

    def _get_creator_works(self, creator_id: str) -> List[Workspace]:
        """
        クリエイターの全投稿を効率的に同期し、Workspaceのリストを返します。
        APIコール前に更新チェックを行うことで、不要なデータ取得をスキップします。
        """
        logger.info(f"クリエイター ({creator_id}) の作品同期を開始します。")
        post_summaries = self._fetch_all_creator_posts_summary(creator_id)
        workspaces: List[Workspace] = []
        total = len(post_summaries)

        for i, (post_id, post_summary_data) in enumerate(post_summaries, 1):
            log = logger.bind(current=i, total=total, post_id=post_id)
            workspace_path = self.repository.get_workspace_path(
                post_id, self.get_provider_name()
            )
            manifest_path = workspace_path / MANIFEST_FILE_NAME

            # APIレスポンスから直接タイムスタンプを取得
            api_timestamp = post_summary_data.get("updatedDatetime", "")

            if not self._perform_pre_flight_check(manifest_path, api_timestamp):
                log.info("コンテンツに変更なし、スキップします。")
                continue

            log.info("--- 投稿を処理中 ---")
            try:
                # _get_single_work は post_id のみを受け取る
                workspace = self._get_single_work(post_id)
                if workspace:
                    workspaces.append(workspace)
            except Exception as e:
                log.bind(error=str(e)).error(
                    "投稿の処理中にエラーが発生しました。",
                    exc_info=self.settings.log_level == "DEBUG",
                )
        return workspaces

    def _get_single_work(self, post_id: str) -> Optional[Workspace]:
        """
        単一の投稿を取得し、Workspaceを生成します。
        有料コンテンツへのアクセス可否を判定し、アクセス不能な場合は
        ワークスペースを作成せずに処理を中断します。
        """
        try:
            # 1. まず投稿の詳細情報を取得
            raw_post_data = self.api_client.post_info(post_id)
            post_data_model = FanboxPostApiResponse.model_validate(raw_post_data)

            # 2. ワークスペースを作成する前にアクセス可能性をチェック
            if not self._is_content_accessible(post_data_model.body):
                logger.bind(post_id=post_id, title=post_data_model.body.title).warning(
                    "有料コンテンツにアクセスできません。スキップします。"
                )
                return None

            # 3. アクセス可能な場合のみワークスペースをセットアップ
            workspace = self.repository.setup_workspace(
                post_id, self.get_provider_name()
            )

            # 4. ワークスペースのクリーンアップ（古いソースを削除）
            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)

            # 5. ワークスペースにコンテンツを処理・格納 (旧Processorの役割)
            metadata = self._process_and_populate_workspace(
                workspace, post_data_model.body
            )

            # 6. メタデータとマニフェストを永続化
            manifest = WorkspaceManifest(
                provider_name=self.get_provider_name(),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                source_metadata={
                    "id": post_id,
                    "creatorId": post_data_model.body.creator_id,
                },
                content_hash=post_data_model.body.updated_datetime,  # content_hashにタイムスタンプを保存
            )
            self.repository.persist_metadata(workspace, metadata, manifest)

            logger.bind(title=metadata.title).success(
                "作品データの処理が完了しました。"
            )
            return workspace

        except Exception as e:
            logger.bind(post_id=post_id, error=str(e)).error(
                "単一投稿の処理中にエラーが発生しました。",
                exc_info=self.settings.log_level == "DEBUG",
            )
            return None

    def _fetch_all_creator_posts_summary(
        self, creator_id: str
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        ページネーションを利用して、クリエイターの全投稿のIDとサマリーデータのタプルリストを取得します。
        (旧 _fetch_all_creator_post_ids の改良版)
        """
        log = logger.bind(creator_id=creator_id)
        log.info("クリエイターの全投稿サマリーの取得を開始")
        summaries: List[Tuple[str, Dict[str, Any]]] = []
        try:
            paginate_response = self.api_client.post_paginate_creator(creator_id)
            page_urls = paginate_response.get("body", [])
            if not isinstance(page_urls, list):
                return []

            for i, page_url in enumerate(page_urls, 1):
                log.debug(f"投稿リスト {i}/{len(page_urls)} ページ目を取得中...")
                list_response = self.api_client.post_list_creator(page_url)
                for item in list_response.get("body", []):
                    if (
                        isinstance(item, dict)
                        and "id" in item
                        and "updatedDatetime" in item
                    ):
                        summaries.append((item["id"], item))
        except Exception as e:
            log.bind(error=str(e)).error("投稿サマリー取得中にエラーが発生しました。")
            return []

        log.bind(count=len(summaries)).info("投稿サマリーの取得が完了しました。")
        return summaries

    def _perform_pre_flight_check(
        self, manifest_path: Path, api_timestamp: str
    ) -> bool:
        """
        APIコール前に、ローカルのマニフェストとAPIのタイムスタンプを比較して更新の要否を判断します。
        """
        if not api_timestamp:
            return True  # タイムスタンプが取得できない場合は、常に更新とみなす
        if not manifest_path.is_file():
            return True  # マニフェストが存在しない = 新規
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            # content_hash フィールドにタイムスタンプが格納されていると仮定
            local_timestamp = manifest_data.get("content_hash")
            return not (local_timestamp and local_timestamp == api_timestamp)
        except (json.JSONDecodeError, IOError):
            return True  # マニフェストが壊れている = 要更新

    def _is_content_accessible(self, post: Post) -> bool:
        """
        投稿が有料かつ本文が取得できない（アクセス不能）状態でないかを確認します。
        """
        # A post is inaccessible if it requires a fee and its body is missing.
        return not (post.fee_required > 0 and post.body is None)

    def _process_and_populate_workspace(
        self, workspace: Workspace, post_data: Post
    ) -> NovelMetadata:
        """
        コンテンツをパースし、画像をダウンロードし、XHTMLを保存し、
        最終的なメタデータを生成して返します。(旧ContentProcessorの役割)
        """
        try:
            image_dir = workspace.assets_path / IMAGES_DIR_NAME
            cover_path = self._downloader.download_cover(post_data, image_dir=image_dir)
            image_paths = self._downloader.download_embedded_images(
                post_data, image_dir=image_dir
            )

            if post_data.body:
                parsed_html = self._parser.parse(post_data.body, image_paths)
                page_path = workspace.source_path / "page-1.xhtml"
                page_path.write_text(parsed_html, encoding="utf-8")

            return self._mapper.map_to_metadata(
                workspace=workspace, cover_path=cover_path, post_data=post_data
            )
        except (ValidationError, KeyError, TypeError) as e:
            raise DataProcessingError(
                f"投稿ID {workspace.id} のデータ解析に失敗: {e}",
                self.get_provider_name(),
            ) from e
