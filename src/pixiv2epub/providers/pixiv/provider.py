# src/pixiv2epub/providers/pixiv/provider.py

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pixivpy3 import PixivError

from ...core.exceptions import DownloadError
from ...core.settings import Settings
from ...models.pixiv import NovelApiResponse, NovelSeriesApiResponse
from ...utils.path_manager import PathManager, generate_sanitized_path
from ..base import BaseProvider
from .client import PixivApiClient
from .downloader import ImageDownloader
from .persister import PixivDataPersister


class PixivProvider(BaseProvider):
    """Pixivから小説データを取得するためのプロバイダ。"""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_client = PixivApiClient(
            refresh_token=self.settings.auth.refresh_token,
            api_delay=self.settings.downloader.api_delay,
            api_retries=self.settings.downloader.api_retries,
        )
        self.base_dir = self.settings.downloader.save_directory

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def get_novel(
        self, novel_id: Any, override_base_dir: Optional[Path] = None
    ) -> Path:
        """単一の小説を取得し、ローカルに保存します。"""
        self.logger.info(f"小説ID: {novel_id} の処理を開始します。")
        try:
            # 1. APIから基本データを取得
            novel_data_dict = self.api_client.webview_novel(novel_id)
            novel_data = NovelApiResponse.from_dict(novel_data_dict)
            detail_data_dict = self.api_client.novel_detail(novel_id)

            # 2. パスを準備
            paths = self._setup_paths(
                novel_data, detail_data_dict, override_base_dir or self.base_dir
            )

            # 3. 画像をダウンロード
            downloader = ImageDownloader(
                self.api_client,
                paths.image_dir,
                self.settings.downloader.overwrite_existing_images,
            )
            cover_path = downloader.download_cover(detail_data_dict.get("novel", {}))
            image_paths = downloader.download_embedded_images(novel_data)

            # 4. テキストとメタデータを永続化
            persister = PixivDataPersister(paths, cover_path, image_paths)
            persister.persist(novel_data, detail_data_dict)

            self.logger.info(
                f"小説「{novel_data.title}」の処理が完了しました。 -> {paths.novel_dir}"
            )
            return paths.novel_dir
        except PixivError as e:
            raise DownloadError(f"小説ID {novel_id} のデータ取得に失敗: {e}") from e
        except Exception as e:
            raise DownloadError(f"小説ID {novel_id} の処理中に予期せぬエラーが発生: {e}") from e

    def get_series(self, series_id: Any) -> List[Path]:
        """シリーズ作品をダウンロードします。"""
        self.logger.info(f"シリーズID: {series_id} の処理を開始します。")
        try:
            series_data = self.get_series_info(series_id)
            series_dir = self._setup_series_dir(series_data)
            novel_ids = [novel.id for novel in series_data.novels]

            if not novel_ids:
                self.logger.info("ダウンロード対象が見つからないため、処理を終了します。")
                return []

            downloaded_paths = []
            total = len(novel_ids)
            self.logger.info(f"計 {total} 件の小説をシリーズフォルダ内にダウンロードします。")

            for i, novel_id in enumerate(novel_ids, 1):
                self.logger.info(f"--- Processing Novel {i}/{total} (ID: {novel_id}) ---")
                try:
                    path = self.get_novel(novel_id, override_base_dir=series_dir)
                    downloaded_paths.append(path)
                except Exception as e:
                    self.logger.error(f"小説ID {novel_id} のダウンロードに失敗: {e}", exc_info=True)

            self.logger.info(f"シリーズ「{series_data.detail.title}」のDLが完了しました。")
            return downloaded_paths
        except Exception as e:
            raise DownloadError(f"シリーズID {series_id} の処理中にエラーが発生: {e}") from e

    def get_series_info(self, series_id: Any) -> NovelSeriesApiResponse:
        """シリーズの小説リストなどの情報を取得します。"""
        try:
            series_data_dict = self.api_client.novel_series(series_id)
            return NovelSeriesApiResponse.from_dict(series_data_dict)
        except PixivError as e:
            raise DownloadError(f"シリーズID {series_id} のメタデータ取得に失敗: {e}") from e

    def get_user_novels(self, user_id: Any) -> List[Path]:
        """ユーザーの全作品をダウンロードします。"""
        self.logger.info(f"ユーザーID: {user_id} の全作品の処理を開始します。")
        try:
            single_ids, series_ids = self._fetch_all_user_novel_ids(user_id)
            self.logger.info(f"取得結果: {len(series_ids)}件のシリーズ、{len(single_ids)}件の単独作品")

            downloaded_paths = []
            if series_ids:
                self.logger.info("--- シリーズ作品の処理を開始 ---")
                for i, s_id in enumerate(series_ids, 1):
                    self.logger.info(f"\n--- Processing Series {i}/{len(series_ids)} ---")
                    try:
                        paths = self.get_series(s_id)
                        downloaded_paths.extend(paths)
                    except Exception as e:
                        self.logger.error(f"シリーズID {s_id} の処理中にエラー: {e}", exc_info=True)

            if single_ids:
                self.logger.info("--- 単独作品の処理を開始 ---")
                for i, n_id in enumerate(single_ids, 1):
                    self.logger.info(f"--- Processing Single Novel {i}/{len(single_ids)} ---")
                    try:
                        path = self.get_novel(n_id)
                        downloaded_paths.append(path)
                    except Exception as e:
                        self.logger.error(f"小説ID {n_id} の処理中にエラー: {e}", exc_info=True)
            return downloaded_paths
        except Exception as e:
            raise DownloadError(f"ユーザーID {user_id} の作品処理中にエラーが発生: {e}") from e

    def _setup_paths(
        self, novel_data: NovelApiResponse, detail_data_dict: Dict, base_dir: Path
    ) -> PathManager:
        template = self.settings.downloader.raw_dir_template
        novel_detail = detail_data_dict.get("novel", {})
        template_vars = {
            "id": novel_data.id,
            "title": novel_data.title,
            "author_name": novel_detail.get("user", {}).get("name", "unknown_author"),
        }
        safe_dir_name = str(generate_sanitized_path(template, template_vars))
        paths = PathManager(base_dir=base_dir, novel_dir_name=safe_dir_name)
        paths.setup_directories()
        return paths

    def _setup_series_dir(self, series_data: NovelSeriesApiResponse) -> Path:
        template = self.settings.downloader.series_dir_template
        template_vars = {
            "id": series_data.detail.id,
            "title": series_data.detail.title,
            "author_name": series_data.detail.user.name,
        }
        safe_dir_name = generate_sanitized_path(template, template_vars)
        series_dir = self.base_dir / safe_dir_name
        series_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"シリーズ保存先ディレクトリ: {series_dir}")
        return series_dir

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