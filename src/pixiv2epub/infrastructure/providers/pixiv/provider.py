# FILE: src/pixiv2epub/infrastructure/providers/pixiv/provider.py
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pixivpy3 import PixivError
from pydantic import ValidationError

from ....models.pixiv import NovelApiResponse, NovelSeriesApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import ApiError, DataProcessingError
from ....shared.settings import Settings
from ...strategies.mappers import PixivMetadataMapper
from ...strategies.parsers import PixivTagParser
from ...strategies.update_checkers import ContentHashUpdateStrategy
from ..base import ICreatorProvider, IMultiWorkProvider, IWorkProvider
from ..base_provider import BaseProvider
from .client import PixivApiClient
from .downloader import ImageDownloader


class PixivProvider(BaseProvider, IWorkProvider, IMultiWorkProvider, ICreatorProvider):
    """Pixivから小説データを取得し、ワークスペースを生成するためのプロバイダ。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_client = PixivApiClient(
            breaker=self.breaker,
            refresh_token=settings.providers.pixiv.refresh_token,
            api_delay=settings.downloader.api_delay,
            api_retries=settings.downloader.api_retries,
        )
        self.update_checker = ContentHashUpdateStrategy()
        self.parser = PixivTagParser()
        self.mapper = PixivMetadataMapper()

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def get_work(self, work_id: Any) -> Optional[Workspace]:
        logger.info("小説ID: {} の処理を開始します。", work_id)
        workspace = self._setup_workspace(work_id)

        try:
            # --- ステップ1: APIからデータを取得し、更新が必要かチェック ---
            novel_data_dict, new_hash, update_required = self._fetch_and_check_update(
                work_id, workspace
            )
            if not update_required:
                logger.info(
                    "コンテンツに変更はありません。処理をスキップします: {}",
                    workspace.id,
                )
                return None

            # --- ステップ2: ワークスペースを準備し、アセットをダウンロード ---
            detail_data_dict = self.api_client.novel_detail(work_id)
            downloader, cover_path = self._download_assets(workspace, detail_data_dict)

            # --- ステップ3: コンテンツを処理し、ワークスペースに保存 ---
            novel_data, image_paths = self._process_and_save_content(
                workspace, novel_data_dict, downloader
            )

            # --- ステップ4: メタデータを生成し、永続化 ---
            self._generate_and_persist_metadata(
                workspace,
                work_id,
                new_hash,
                novel_data,
                detail_data_dict,
                cover_path,
                image_paths,
            )

            logger.info(
                "小説「{}」のデータ取得が完了しました -> {}",
                novel_data.title,
                workspace.root_path,
            )
            return workspace

        except (PixivError, ApiError) as e:
            raise ApiError(
                f"小説ID {work_id} のデータ取得に失敗: {e}", self.get_provider_name()
            ) from e
        except (ValidationError, KeyError, TypeError) as e:
            raise DataProcessingError(
                f"小説ID {work_id} のデータ解析に失敗: {e}"
            ) from e

    # ステップ1: API呼び出しと更新チェック
    def _fetch_and_check_update(
        self, work_id: int, workspace: Workspace
    ) -> Tuple[Dict, str, bool]:
        novel_data_dict = self.api_client.webview_novel(work_id)
        update_required, new_hash = self.update_checker.is_update_required(
            workspace, novel_data_dict
        )
        if update_required:
            logger.info(
                "コンテンツの更新を検出しました（または新規ダウンロードです）。"
            )
            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)
        return novel_data_dict, new_hash, update_required

    # ステップ2: アセットのダウンロード
    def _download_assets(
        self, workspace: Workspace, detail_data_dict: Dict
    ) -> Tuple[ImageDownloader, Optional[Path]]:
        downloader = ImageDownloader(
            self.api_client,
            workspace.assets_path / "images",
            self.settings.downloader.overwrite_existing_images,
        )
        cover_path = downloader.download_cover(detail_data_dict.get("novel", {}))
        return downloader, cover_path

    # ステップ3: コンテンツのパースと保存
    def _process_and_save_content(
        self, workspace: Workspace, novel_data_dict: Dict, downloader: ImageDownloader
    ) -> Tuple[NovelApiResponse, Dict[str, Path]]:
        novel_data = NovelApiResponse.model_validate(novel_data_dict)
        image_paths = downloader.download_embedded_images(novel_data)
        parsed_text = self.parser.parse(novel_data.text, image_paths)

        pages = parsed_text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = workspace.source_path / f"page-{i + 1}.xhtml"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_content)
            except IOError as e:
                logger.error("ページ {} の保存に失敗しました: {}", i + 1, e)
        logger.debug("{}ページの保存が完了しました。", len(pages))

        return novel_data, image_paths

    # ステップ4: メタデータの生成と永続化
    def _generate_and_persist_metadata(
        self,
        workspace: Workspace,
        work_id: int,
        new_hash: str,
        novel_data: NovelApiResponse,
        detail_data_dict: Dict,
        cover_path: Optional[Path],
        image_paths: Dict[str, Path],
    ):
        parsed_description = self.parser.parse(
            detail_data_dict.get("novel", {}).get("caption", ""), image_paths
        )

        # NOTE: parsed_text is needed again here for page title extraction in mapper
        parsed_text = self.parser.parse(novel_data.text, image_paths)

        metadata = self.mapper.map_to_metadata(
            workspace=workspace,
            cover_path=cover_path,
            novel_data=novel_data,
            detail_data=detail_data_dict,
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
        logger.info("シリーズID: {} の処理を開始します。", series_id)
        try:
            series_data = self.get_series_info(series_id)
            novel_ids = [novel.id for novel in series_data.novels]

            if not novel_ids:
                logger.info("ダウンロード対象が見つからないため、処理を終了します。")
                return []

            downloaded_workspaces = []
            total = len(novel_ids)
            logger.info("計 {} 件の小説をダウンロードします。", total)

            for i, novel_id in enumerate(novel_ids, 1):
                logger.info("--- 処理中 {}/{} (ID: {}) ---", i, total, novel_id)
                try:
                    workspace = self.get_work(novel_id)
                    if workspace:
                        downloaded_workspaces.append(workspace)
                except Exception as e:
                    logger.error(
                        "小説ID {} のダウンロードに失敗: {}", novel_id, e, exc_info=True
                    )

            logger.info(
                "シリーズ「{}」のDLが完了しました。",
                series_data.novel_series_detail.title,
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
        logger.info("ユーザーID: {} の全作品の処理を開始します。", user_id)
        try:
            single_ids, series_ids = self._fetch_all_user_novel_ids(user_id)
            logger.info(
                "取得結果: {}件のシリーズ、{}件の単独作品",
                len(series_ids),
                len(single_ids),
            )

            downloaded_workspaces = []
            if series_ids:
                logger.info("--- シリーズ作品の処理を開始 ---")
                for i, s_id in enumerate(series_ids, 1):
                    logger.info("\n--- シリーズ処理中 {}/{} ---", i, len(series_ids))
                    try:
                        workspaces = self.get_multiple_works(s_id)
                        downloaded_workspaces.extend(workspaces)
                    except Exception as e:
                        logger.error(
                            "シリーズID {} の処理中にエラー: {}", s_id, e, exc_info=True
                        )

            if single_ids:
                logger.info("--- 単独作品の処理を開始 ---")
                for i, n_id in enumerate(single_ids, 1):
                    logger.info("--- 単独作品処理中 {}/{} ---", i, len(single_ids))
                    try:
                        workspace = self.get_work(n_id)
                        if workspace:
                            downloaded_workspaces.append(workspace)
                    except Exception as e:
                        logger.error(
                            "小説ID {} の処理中にエラー: {}", n_id, e, exc_info=True
                        )
            return downloaded_workspaces
        except Exception as e:
            raise ApiError(
                f"ユーザーID {user_id} の作品処理中にエラーが発生: {e}",
                self.get_provider_name(),
            ) from e

    def _fetch_all_user_novel_ids(self, user_id: int) -> Tuple[List[int], List[int]]:
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
