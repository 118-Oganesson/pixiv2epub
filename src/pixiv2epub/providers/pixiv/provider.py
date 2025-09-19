#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/providers/pixiv/provider.py
#
# Pixivから小説データをダウンロードするための具体的な実装。
# BaseProviderインターフェースを実装し、データ取得処理を統括します。
# -----------------------------------------------------------------------------

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ... import constants as const
from ...data_models import NovelApiResponse, NovelSeriesApiResponse
from ...utils.path_manager import PathManager, generate_sanitized_path
from ..base_provider import BaseProvider
from .api_client import PixivApiClient
from .persister import PixivDataPersister


class PixivProvider(BaseProvider):
    """Pixivから小説データを取得するためのプロバイダ。"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        auth_conf = self.config.get(const.KEY_AUTH, {})
        downloader_conf = self.config.get(const.KEY_DOWNLOADER, {})

        self.api_client = PixivApiClient(
            refresh_token=auth_conf.get(const.KEY_REFRESH_TOKEN),
            api_delay=float(
                downloader_conf.get(const.KEY_API_DELAY, const.DEFAULT_API_DELAY)
            ),
            api_retries=int(
                downloader_conf.get(const.KEY_API_RETRIES, const.DEFAULT_API_RETRIES)
            ),
        )
        self.base_dir = Path(
            downloader_conf.get(const.KEY_SAVE_DIRECTORY, const.DEFAULT_RAW_DATA_DIR)
        )

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def get_novel(
        self, novel_id: Any, override_base_dir: Optional[Path] = None
    ) -> Path:
        """単一の小説を取得し、ローカルに保存します。"""
        self.logger.info(f"小説ID: {novel_id} の処理を開始します。")

        # 1. APIからデータを取得
        novel_data_dict = self.api_client.webview_novel(novel_id)
        novel_data = NovelApiResponse.from_dict(novel_data_dict)
        detail_data_dict = self.api_client.novel_detail(novel_id)

        # 2. パスを準備
        paths = self._setup_paths(
            novel_data, detail_data_dict, override_base_dir or self.base_dir
        )

        # 3. 保存処理をPersisterに委譲
        persister = PixivDataPersister(self.config, paths, self.api_client)
        persister.persist(novel_data, detail_data_dict)

        self.logger.info(
            f"小説「{novel_data.title}」の処理が完了しました。 -> {paths.novel_dir}"
        )
        return paths.novel_dir

    def get_series(
        self, series_id: Any, novel_ids_to_download: Optional[List[int]] = None
    ) -> List[Path]:
        """シリーズ作品をダウンロードします。"""
        self.logger.info(f"シリーズID: {series_id} の処理を開始します。")
        series_data = self.get_series_info(series_id)

        series_dir = self._setup_series_dir(series_data)

        if novel_ids_to_download is None:
            novel_ids_to_download = [novel.id for novel in series_data.novels]

        if not novel_ids_to_download:
            self.logger.info("ダウンロード対象が見つからないため、処理を終了します。")
            return []

        downloaded_paths = []
        total = len(novel_ids_to_download)
        self.logger.info(
            f"計 {total} 件の小説をシリーズフォルダ内にダウンロードします。"
        )

        for i, novel_id in enumerate(novel_ids_to_download, 1):
            self.logger.info(f"--- Processing Novel {i}/{total} (ID: {novel_id}) ---")
            try:
                path = self.get_novel(novel_id, override_base_dir=series_dir)
                downloaded_paths.append(path)
            except Exception as e:
                self.logger.error(
                    f"小説ID {novel_id} のダウンロードに失敗: {e}", exc_info=True
                )

        self.logger.info(
            f"シリーズ「{series_data.detail.title}」のダウンロードが完了しました。"
        )
        return downloaded_paths

    def get_series_info(self, series_id: Any) -> NovelSeriesApiResponse:
        """シリーズの小説リストなどの情報を取得します。"""
        self.logger.debug(f"シリーズID: {series_id} の情報を取得します。")
        series_data_dict = self.api_client.novel_series(series_id)
        return NovelSeriesApiResponse.from_dict(series_data_dict)

    def get_user_novels(self, user_id: Any) -> List[Path]:
        """ユーザーの全作品をダウンロードします。"""
        self.logger.info(f"ユーザーID: {user_id} の全作品の処理を開始します。")

        single_novel_ids, series_ids = self._fetch_all_user_novel_ids(user_id)

        self.logger.info(
            f"取得結果: {len(series_ids)}件のシリーズ、{len(single_novel_ids)}件の単独作品が見つかりました。"
        )

        downloaded_paths = []
        if series_ids:
            self.logger.info("--- Processing Series ---")
            for i, series_id in enumerate(series_ids, 1):
                self.logger.info(f"\n--- Processing Series {i}/{len(series_ids)} ---")
                try:
                    paths = self.get_series(series_id)
                    downloaded_paths.extend(paths)
                except Exception as e:
                    self.logger.error(
                        f"シリーズID {series_id} の処理中にエラー: {e}", exc_info=True
                    )

        if single_novel_ids:
            self.logger.info("--- Processing Single Novels ---")
            for i, novel_id in enumerate(single_novel_ids, 1):
                self.logger.info(
                    f"--- Processing Single Novel {i}/{len(single_novel_ids)} ---"
                )
                try:
                    path = self.get_novel(novel_id)
                    downloaded_paths.append(path)
                except Exception as e:
                    self.logger.error(
                        f"小説ID {novel_id} の処理中にエラー: {e}", exc_info=True
                    )

        return downloaded_paths

    # --- Private Helper Methods ---

    def _setup_paths(
        self, novel_data: NovelApiResponse, detail_data_dict: Dict, base_dir: Path
    ) -> PathManager:
        """ダウンロードファイルの保存先パスを準備します。"""
        downloader_conf = self.config.get(const.KEY_DOWNLOADER, {})
        template = downloader_conf.get(
            const.KEY_RAW_DIR_TEMPLATE, const.DEFAULT_NOVEL_DIR_TEMPLATE
        )

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
        """シリーズ用の親ディレクトリパスを準備します。"""
        downloader_conf = self.config.get(const.KEY_DOWNLOADER, {})
        template = downloader_conf.get(
            const.KEY_SERIES_DIR_TEMPLATE, const.DEFAULT_SERIES_DIR_TEMPLATE
        )

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
        single_novel_ids, series_ids = [], set()
        next_url = None
        while True:
            res = self.api_client.user_novels(user_id, next_url)
            for novel in res.get("novels", []):
                if novel.get("series") and novel["series"].get("id"):
                    series_ids.add(novel["series"]["id"])
                else:
                    single_novel_ids.append(novel["id"])

            next_url = res.get("next_url")
            if not next_url:
                break
        return single_novel_ids, series_ids
