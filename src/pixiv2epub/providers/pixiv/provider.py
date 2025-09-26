# src/pixiv2epub/providers/pixiv/provider.py

import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, List, Set, Tuple

from pixivpy3 import PixivError

from ...core.exceptions import DownloadError
from ...core.settings import Settings
from ...models.pixiv import NovelApiResponse, NovelSeriesApiResponse
from ...models.workspace import Workspace, WorkspaceManifest
from ..base import BaseProvider
from .client import PixivApiClient
from .downloader import ImageDownloader
from .persister import PixivDataPersister


class PixivProvider(BaseProvider):
    """Pixivから小説データを取得し、ワークスペースを生成するためのプロバイダ。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_client = PixivApiClient(
            refresh_token=self.settings.auth.refresh_token,
            api_delay=self.settings.downloader.api_delay,
            api_retries=self.settings.downloader.api_retries,
        )
        self.workspace_dir = self.settings.workspace.root_directory

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def _create_workspace(self) -> Workspace:
        """一意のIDを持つ新しいワークスペースを初期化します。"""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        workspace_id = str(uuid.uuid4())
        workspace_path = self.workspace_dir / workspace_id
        workspace = Workspace(id=workspace_id, root_path=workspace_path)

        # 必須ディレクトリを作成
        workspace.source_path.mkdir(parents=True)
        (workspace.assets_path / "images").mkdir(parents=True)

        self.logger.debug(f"ワークスペースを作成しました: {workspace.root_path}")
        return workspace

    def get_novel(self, novel_id: Any) -> Workspace:
        """単一の小説を取得し、ローカルに保存します。"""
        self.logger.info(f"小説ID: {novel_id} の処理を開始します。")
        workspace = self._create_workspace()
        try:
            # 1. APIから基本データを取得
            novel_data_dict = self.api_client.webview_novel(novel_id)
            novel_data = NovelApiResponse.from_dict(novel_data_dict)
            detail_data_dict = self.api_client.novel_detail(novel_id)

            # 2. 画像をダウンロード
            image_dir = workspace.assets_path / "images"
            downloader = ImageDownloader(
                self.api_client,
                image_dir,
                self.settings.downloader.overwrite_existing_images,
            )
            cover_path = downloader.download_cover(detail_data_dict.get("novel", {}))
            image_paths = downloader.download_embedded_images(novel_data)

            # 3. manifest.json を準備
            manifest = WorkspaceManifest(
                provider_name=self.get_provider_name(),
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                source_metadata={"novel_id": novel_id},
            )

            # 4. テキストとメタデータを永続化
            persister = PixivDataPersister(workspace, cover_path, image_paths)
            persister.persist(novel_data, detail_data_dict, manifest)

            self.logger.info(
                f"小説「{novel_data.title}」のデータ取得が完了しました -> {workspace.root_path}"
            )
            return workspace
        except Exception as e:
            # エラー発生時は作成したワークスペースをクリーンアップ
            shutil.rmtree(workspace.root_path, ignore_errors=True)
            if isinstance(e, PixivError):
                raise DownloadError(f"小説ID {novel_id} のデータ取得に失敗: {e}") from e
            raise DownloadError(
                f"小説ID {novel_id} の処理中に予期せぬエラーが発生: {e}"
            ) from e

    def get_series(self, series_id: Any) -> List[Workspace]:
        """シリーズ作品をダウンロードします。"""
        self.logger.info(f"シリーズID: {series_id} の処理を開始します。")
        try:
            series_data = self.get_series_info(series_id)
            novel_ids = [novel.id for novel in series_data.novels]

            if not novel_ids:
                self.logger.info(
                    "ダウンロード対象が見つからないため、処理を終了します。"
                )
                return []

            downloaded_workspaces = []
            total = len(novel_ids)
            self.logger.info(f"計 {total} 件の小説をダウンロードします。")

            for i, novel_id in enumerate(novel_ids, 1):
                self.logger.info(
                    f"--- Processing Novel {i}/{total} (ID: {novel_id}) ---"
                )
                try:
                    workspace = self.get_novel(novel_id)
                    downloaded_workspaces.append(workspace)
                except Exception as e:
                    self.logger.error(
                        f"小説ID {novel_id} のダウンロードに失敗: {e}", exc_info=True
                    )

            self.logger.info(
                f"シリーズ「{series_data.detail.title}」のDLが完了しました。"
            )
            return downloaded_workspaces
        except Exception as e:
            raise DownloadError(
                f"シリーズID {series_id} の処理中にエラーが発生: {e}"
            ) from e

    def get_series_info(self, series_id: Any) -> NovelSeriesApiResponse:
        """シリーズの小説リストなどの情報を取得します。"""
        try:
            series_data_dict = self.api_client.novel_series(series_id)
            return NovelSeriesApiResponse.from_dict(series_data_dict)
        except PixivError as e:
            raise DownloadError(
                f"シリーズID {series_id} のメタデータ取得に失敗: {e}"
            ) from e

    def get_user_novels(self, user_id: Any) -> List[Workspace]:
        """ユーザーの全作品をダウンロードします。"""
        self.logger.info(f"ユーザーID: {user_id} の全作品の処理を開始します。")
        try:
            single_ids, series_ids = self._fetch_all_user_novel_ids(user_id)
            self.logger.info(
                f"取得結果: {len(series_ids)}件のシリーズ、{len(single_ids)}件の単独作品"
            )

            downloaded_workspaces = []
            if series_ids:
                self.logger.info("--- シリーズ作品の処理を開始 ---")
                for i, s_id in enumerate(series_ids, 1):
                    self.logger.info(
                        f"\n--- Processing Series {i}/{len(series_ids)} ---"
                    )
                    try:
                        workspaces = self.get_series(s_id)
                        downloaded_workspaces.extend(workspaces)
                    except Exception as e:
                        self.logger.error(
                            f"シリーズID {s_id} の処理中にエラー: {e}", exc_info=True
                        )

            if single_ids:
                self.logger.info("--- 単独作品の処理を開始 ---")
                for i, n_id in enumerate(single_ids, 1):
                    self.logger.info(
                        f"--- Processing Single Novel {i}/{len(single_ids)} ---"
                    )
                    try:
                        workspace = self.get_novel(n_id)
                        downloaded_workspaces.append(workspace)
                    except Exception as e:
                        self.logger.error(
                            f"小説ID {n_id} の処理中にエラー: {e}", exc_info=True
                        )
            return downloaded_workspaces
        except Exception as e:
            raise DownloadError(
                f"ユーザーID {user_id} の作品処理中にエラーが発生: {e}"
            ) from e

    def _fetch_all_user_novel_ids(self, user_id: int) -> Tuple[List[int], Set[int]]:
        """ページネーションをたどり、ユーザーの全小説IDとシリーズIDを取得します。"""
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
