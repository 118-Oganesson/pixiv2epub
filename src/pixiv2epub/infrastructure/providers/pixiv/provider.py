# FILE: src/pixiv2epub/infrastructure/providers/pixiv/provider.py
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pixivpy3 import PixivError
from pydantic import ValidationError
from pybreaker import CircuitBreaker

from ....domain.interfaces import (
    ICreatorProvider,
    IMultiWorkProvider,
    IWorkProvider,
    IPixivImageDownloader,
)
from ....models.pixiv import NovelApiResponse, NovelSeriesApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import ApiError, DataProcessingError
from ....shared.settings import Settings
from ...strategies.mappers import PixivMetadataMapper
from ...strategies.parsers import PixivTagParser
from ...strategies.update_checkers import ContentHashUpdateStrategy
from ..base_provider import BaseProvider
from .client import PixivApiClient


class PixivProvider(BaseProvider, IWorkProvider, IMultiWorkProvider, ICreatorProvider):
    """Pixivから小説データを取得し、ワークスペースを生成するためのプロバイダ。"""

    def __init__(
        self,
        settings: Settings,
        api_client: PixivApiClient,
        downloader: IPixivImageDownloader,
        breaker: CircuitBreaker,
    ):
        """
        Args:
            settings (Settings): アプリケーション設定。
            api_client (PixivApiClient): 認証済みのPixiv APIクライアント。
            downloader (IPixivImageDownloader): Pixiv画像ダウンロード用インターフェース。
            breaker (CircuitBreaker): 共有サーキットブレーカーインスタンス。
        """
        super().__init__(settings, breaker)
        self.api_client = api_client
        self.downloader = downloader

        # 戦略オブジェクトのインスタンス化
        self.update_checker = ContentHashUpdateStrategy()
        self.parser = PixivTagParser()
        self.mapper = PixivMetadataMapper()

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def get_work(self, work_id: Any) -> Optional[Workspace]:
        with logger.contextualize(provider=self.get_provider_name(), work_id=work_id):
            logger.info("小説の処理を開始")
            workspace = self._setup_workspace(work_id)

            try:
                # --- ステップ1: APIからデータを取得し、更新が必要かチェック ---
                raw_webview_novel_data, new_hash, update_required = (
                    self._fetch_and_check_update(work_id, workspace)
                )
                if not update_required:
                    logger.bind(workspace_id=workspace.id).info(
                        "コンテンツに変更なし、スキップします。"
                    )
                    return None

                # --- ステップ2: ワークスペースを準備し、アセットをダウンロード ---
                raw_novel_detail_data = self.api_client.novel_detail(work_id)
                cover_path = self._download_assets(workspace, raw_novel_detail_data)

                # --- ステップ3: コンテンツを処理し、ワークスペースに保存 ---
                novel_data, image_paths, parsed_text = self._process_and_save_content(
                    workspace, raw_webview_novel_data
                )

                # --- ステップ4: メタデータを生成し、永続化 ---
                self._generate_and_persist_metadata(
                    workspace=workspace,
                    work_id=work_id,
                    new_hash=new_hash,
                    novel_data=novel_data,
                    detail_data=raw_novel_detail_data,
                    cover_path=cover_path,
                    image_paths=image_paths,
                    parsed_text=parsed_text,
                )

                logger.bind(
                    title=novel_data.title, workspace_path=str(workspace.root_path)
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

    def _fetch_and_check_update(
        self, work_id: int, workspace: Workspace
    ) -> Tuple[Dict, str, bool]:
        """APIからデータを取得し、更新が必要かチェックします。"""
        raw_webview_novel_data = self.api_client.webview_novel(work_id)
        update_required, new_hash = self.update_checker.is_update_required(
            workspace, raw_webview_novel_data
        )
        if update_required:
            logger.info("コンテンツの更新を検出（または新規ダウンロードです）。")
            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)
        return raw_webview_novel_data, new_hash, update_required

    def _download_assets(
        self, workspace: Workspace, raw_novel_detail_data: Dict
    ) -> Optional[Path]:
        """注入されたダウンローダーを使い、アセットをダウンロードします。"""
        image_dir = workspace.assets_path / "images"
        cover_path = self.downloader.download_cover(
            raw_novel_detail_data.get("novel", {}), image_dir=image_dir
        )
        return cover_path

    def _process_and_save_content(
        self,
        workspace: Workspace,
        raw_webview_novel_data: Dict,
    ) -> Tuple[NovelApiResponse, Dict[str, Path], str]:
        """コンテンツをパースし、画像をダウンロードし、XHTMLを保存します。"""
        novel_data = NovelApiResponse.model_validate(raw_webview_novel_data)

        image_dir = workspace.assets_path / "images"
        image_paths = self.downloader.download_embedded_images(
            novel_data, image_dir=image_dir
        )

        parsed_text = self.parser.parse(novel_data.text, image_paths)

        pages = parsed_text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = workspace.source_path / f"page-{i + 1}.xhtml"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_content)
            except IOError as e:
                logger.bind(page=i + 1, error=str(e)).error(
                    "ページの保存に失敗しました。"
                )
        logger.bind(page_count=len(pages)).debug("ページの保存が完了しました。")

        return novel_data, image_paths, parsed_text

    def _generate_and_persist_metadata(
        self,
        workspace: Workspace,
        work_id: int,
        new_hash: str,
        novel_data: NovelApiResponse,
        detail_data: Dict,
        cover_path: Optional[Path],
        image_paths: Dict[str, Path],
        parsed_text: str,
    ):
        """メタデータを生成し、manifest.json と detail.json を保存します。"""
        parsed_description = self.parser.parse(
            detail_data.get("novel", {}).get("caption", ""), image_paths
        )

        metadata = self.mapper.map_to_metadata(
            workspace=workspace,
            cover_path=cover_path,
            novel_data=novel_data,
            detail_data=detail_data,
            parsed_text=parsed_text,
            parsed_description=parsed_description,
        )
        manifest = WorkspaceManifest(
            provider_name=self.get_provider_name(),
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            source_metadata={"novel_id": work_id},
            content_hash=new_hash,
        )
        self._persist_metadata(workspace, metadata, manifest)

    def get_multiple_works(self, series_id: Any) -> List[Workspace]:
        with logger.contextualize(
            provider=self.get_provider_name(), series_id=series_id
        ):
            logger.info("シリーズの処理を開始")
            try:
                series_data = self.get_series_info(series_id)
                novel_ids = [novel.id for novel in series_data.novels]

                if not novel_ids:
                    logger.info("ダウンロード対象が見つからず処理を終了します。")
                    return []

                downloaded_workspaces = []
                total = len(novel_ids)
                logger.bind(total_novels=total).info(
                    "シリーズ内の小説ダウンロードを開始"
                )

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
        with logger.contextualize(provider=self.get_provider_name(), user_id=user_id):
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
                        log = logger.bind(
                            current_series=i, total_series=len(series_ids)
                        )
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
