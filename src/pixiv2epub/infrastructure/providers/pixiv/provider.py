# FILE: src/pixiv2epub/infrastructure/providers/pixiv/provider.py
import shutil
from datetime import datetime, timezone
from typing import Any, List, Set, Tuple

from loguru import logger
from pixivpy3 import PixivError
from pydantic import ValidationError

from ....models.pixiv import NovelApiResponse, NovelSeriesApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.exceptions import ApiError, DataProcessingError
from ....shared.settings import Settings
from ..base import ICreatorProvider, IMultiWorkProvider, IWorkProvider
from ..base_provider import BaseProvider
from ...strategies.mappers import PixivMetadataMapper
from ...strategies.parsers import PixivTagParser
from ...strategies.update_checkers import ContentHashUpdateStrategy
from .client import PixivApiClient
from .downloader import ImageDownloader


class PixivProvider(BaseProvider, IWorkProvider, IMultiWorkProvider, ICreatorProvider):
    """Pixivから小説データを取得し、ワークスペースを生成するためのプロバイダ。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_client = PixivApiClient(
            refresh_token=self.settings.providers.pixiv.refresh_token,
            api_delay=self.settings.downloader.api_delay,
            api_retries=self.settings.downloader.api_retries,
        )
        # 戦略オブジェクトをインスタンス化
        self.update_checker = ContentHashUpdateStrategy()
        self.parser = PixivTagParser()
        self.mapper = PixivMetadataMapper()

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def _save_pages(self, workspace: Workspace, parsed_text: str):
        pages = parsed_text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = workspace.source_path / f"page-{i + 1}.xhtml"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_content)
            except IOError as e:
                logger.error(f"ページ {i + 1} の保存に失敗しました: {e}")
        logger.debug(f"{len(pages)}ページの保存が完了しました。")

    def get_work(self, work_id: Any) -> Workspace:
        logger.info(f"小説ID: {work_id} の処理を開始します。")
        workspace = self._setup_workspace(work_id)

        try:
            # --- Network and Download Operations ---
            novel_data_dict = self.api_client.webview_novel(work_id)

            update_required, new_hash = self.update_checker.is_update_required(
                workspace, novel_data_dict
            )

            if not update_required:
                logger.info(
                    f"コンテンツに変更はありません。処理をスキップします: {workspace.id}"
                )
                return workspace

            logger.info(
                "コンテンツの更新を検出しました（または新規ダウンロードです）。"
            )
            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)

            detail_data_dict = self.api_client.novel_detail(work_id)
            downloader = ImageDownloader(
                self.api_client,
                workspace.assets_path / "images",
                self.settings.downloader.overwrite_existing_images,
            )
            cover_path = downloader.download_cover(detail_data_dict.get("novel", {}))

        except (PixivError, ApiError) as e:
            raise ApiError(
                f"小説ID {work_id} のデータ取得に失敗: {e}", self.get_provider_name()
            ) from e

        try:
            # --- Data Processing and Mapping Operations ---
            novel_data = NovelApiResponse.from_dict(novel_data_dict)
            image_paths = downloader.download_embedded_images(novel_data)

            parsed_text = self.parser.parse(novel_data.text, image_paths)
            self._save_pages(workspace, parsed_text)
            parsed_description = self.parser.parse(
                detail_data_dict.get("novel", {}).get("caption", ""), image_paths
            )

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

            logger.info(
                f"小説「{novel_data.title}」のデータ取得が完了しました -> {workspace.root_path}"
            )
            return workspace

        except (ValidationError, KeyError, TypeError) as e:
            raise DataProcessingError(
                f"小説ID {work_id} のデータ解析に失敗: {e}"
            ) from e

    def get_multiple_works(self, series_id: Any) -> List[Workspace]:
        logger.info(f"シリーズID: {series_id} の処理を開始します。")
        try:
            series_data = self.get_series_info(series_id)
            novel_ids = [novel.id for novel in series_data.novels]

            if not novel_ids:
                logger.info("ダウンロード対象が見つからないため、処理を終了します。")
                return []

            downloaded_workspaces = []
            total = len(novel_ids)
            logger.info(f"計 {total} 件の小説をダウンロードします。")

            for i, novel_id in enumerate(novel_ids, 1):
                logger.info(f"--- Processing Novel {i}/{total} (ID: {novel_id}) ---")
                try:
                    workspace = self.get_work(novel_id)
                    downloaded_workspaces.append(workspace)
                except Exception as e:
                    logger.error(
                        f"小説ID {novel_id} のダウンロードに失敗: {e}", exc_info=True
                    )

            logger.info(f"シリーズ「{series_data.detail.title}」のDLが完了しました。")
            return downloaded_workspaces
        except Exception as e:
            raise ApiError(
                f"シリーズID {series_id} の処理中にエラーが発生: {e}",
                self.get_provider_name(),
            ) from e

    def get_series_info(self, series_id: Any) -> NovelSeriesApiResponse:
        try:
            series_data_dict = self.api_client.novel_series(series_id)
            return NovelSeriesApiResponse.from_dict(series_data_dict)
        except PixivError as e:
            raise ApiError(
                f"シリーズID {series_id} のメタデータ取得に失敗: {e}",
                self.get_provider_name(),
            ) from e

    def get_creator_works(self, user_id: Any) -> List[Workspace]:
        logger.info(f"ユーザーID: {user_id} の全作品の処理を開始します。")
        try:
            single_ids, series_ids = self._fetch_all_user_novel_ids(user_id)
            logger.info(
                f"取得結果: {len(series_ids)}件のシリーズ、{len(single_ids)}件の単独作品"
            )

            downloaded_workspaces = []
            if series_ids:
                logger.info("--- シリーズ作品の処理を開始 ---")
                for i, s_id in enumerate(series_ids, 1):
                    logger.info(f"\n--- Processing Series {i}/{len(series_ids)} ---")
                    try:
                        workspaces = self.get_multiple_works(s_id)
                        downloaded_workspaces.extend(workspaces)
                    except Exception as e:
                        logger.error(
                            f"シリーズID {s_id} の処理中にエラー: {e}", exc_info=True
                        )

            if single_ids:
                logger.info("--- 単独作品の処理を開始 ---")
                for i, n_id in enumerate(single_ids, 1):
                    logger.info(
                        f"--- Processing Single Novel {i}/{len(single_ids)} ---"
                    )
                    try:
                        workspace = self.get_work(n_id)
                        downloaded_workspaces.append(workspace)
                    except Exception as e:
                        logger.error(
                            f"小説ID {n_id} の処理中にエラー: {e}", exc_info=True
                        )
            return downloaded_workspaces
        except Exception as e:
            raise ApiError(
                f"ユーザーID {user_id} の作品処理中にエラーが発生: {e}",
                self.get_provider_name(),
            ) from e

    def _fetch_all_user_novel_ids(self, user_id: int) -> Tuple[List[int], Set[int]]:
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
        return single_ids, series_ids
