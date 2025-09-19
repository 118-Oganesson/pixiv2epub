#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/providers/pixiv/downloader.py
#
# Pixivから小説データをダウンロードするための具体的な実装。
# BaseProviderインターフェースを実装し、ダウンロード処理全体を統括します。
# -----------------------------------------------------------------------------

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ... import constants as const
from ...data_models import NovelApiResponse, NovelSeriesApiResponse
from ...utils.path_manager import PathManager
from ..base_provider import BaseProvider
from .api_client import PixivApiClient
from .parser import PixivParser


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
        self.overwrite_images = bool(
            downloader_conf.get(const.KEY_OVERWRITE_IMAGES, False)
        )

        # 小説ごとの状態を保持する変数
        self.paths: Optional[PathManager] = None
        self.image_paths: Dict[str, str] = {}
        self.parser: Optional[PixivParser] = None

    @classmethod
    def get_provider_name(cls) -> str:
        return "pixiv"

    def get_novel(
        self, novel_id: Any, override_base_dir: Optional[Path] = None
    ) -> Path:
        """単一の小説をダウンロードします。"""
        self.logger.info(f"小説ID: {novel_id} のダウンロードを開始します。")
        self.image_paths = {}

        # 1. データ取得と保存先準備
        novel_data_dict = self.api_client.webview_novel(novel_id)
        novel_data = NovelApiResponse.from_dict(novel_data_dict)
        detail_data_dict = self.api_client.novel_detail(novel_id)

        self._setup_paths(
            novel_data, detail_data_dict, override_base_dir or self.base_dir
        )
        self.parser = PixivParser(self.image_paths)

        # 2. アセット（画像）のダウンロード
        self._prepare_and_download_all_images(novel_data)

        # 3. メタデータと本文の保存
        self._save_detail_json(novel_data, detail_data_dict)
        self._save_pages(novel_data)

        self.logger.info(
            f"小説「{novel_data.title}」のダウンロードが完了しました。 -> {self.paths.novel_dir}"
        )
        return self.paths.novel_dir

    def get_series(
        self, series_id: Any, novel_ids_to_download: Optional[List[int]] = None
    ) -> List[Path]:
        """
        シリーズ作品をダウンロードします。

        Args:
            series_id (Any): シリーズID。
            novel_ids_to_download (Optional[List[int]]): ダウンロード対象の小説IDリスト。
                Noneの場合はシリーズ内の全小説をダウンロードします。
        """
        self.logger.info(f"シリーズID: {series_id} の処理を開始します。")
        series_data = self.get_series_info(series_id)

        series_dir = self._setup_series_dir(series_data)

        # もしダウンロード対象のIDが指定されていなければ、シリーズ内の全小説を対象とする
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
        """シリーズの小説リストなどの情報を取得します。UIでの選択肢表示用です。"""
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
    ):
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
        relative_path_str = template.format(**template_vars)

        safe_parts = [
            re.sub(const.INVALID_PATH_CHARS_REGEX, "_", part).strip()
            for part in relative_path_str.split("/")
        ]
        safe_dir_name = "/".join(safe_parts)

        self.paths = PathManager(base_dir=base_dir, novel_dir_name=safe_dir_name)
        self.paths.setup_directories()

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
        relative_path_str = template.format(**template_vars)

        safe_parts = [
            re.sub(const.INVALID_PATH_CHARS_REGEX, "_", part).strip()
            for part in relative_path_str.split("/")
        ]
        safe_dir_name = Path(*safe_parts)

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

    def _download_image(self, url: str, filename: str) -> Optional[str]:
        """単一の画像をダウンロードし、メタデータ用の相対パスを返します。"""
        target_path = self.paths.image_dir / filename
        # detail.jsonに保存するパスは、常にnovel_dirからの相対パスとする
        relative_path_for_meta = f"./{const.IMAGES_DIR_NAME}/{filename}"

        if target_path.exists() and not self.overwrite_images:
            return relative_path_for_meta

        try:
            self.api_client.download(url, path=self.paths.image_dir, name=filename)
            return relative_path_for_meta
        except Exception as e:
            self.logger.warning(f"画像 ({url}) のダウンロードに失敗しました: {e}")
            return None

    def _prepare_and_download_all_images(self, novel_data: NovelApiResponse):
        """本文中のすべての画像をダウンロードします。"""
        self.logger.info("画像のダウンロードを開始します...")
        text = novel_data.text
        uploaded_ids = set(re.findall(r"\[uploadedimage:(\d+)\]", text))
        pixiv_ids = set(re.findall(r"\[pixivimage:(\d+)\]", text))

        total_images = len(uploaded_ids) + len(pixiv_ids)
        self.logger.info(f"対象画像: {total_images}件")

        for image_id in uploaded_ids:
            image_meta = novel_data.images.get(image_id)
            if image_meta and image_meta.urls.original:
                url = image_meta.urls.original
                ext = url.split(".")[-1].split("?")[0]
                filename = f"uploaded_{image_id}.{ext}"
                if path := self._download_image(url, filename):
                    self.image_paths[image_id] = path

        for illust_id in pixiv_ids:
            try:
                illust_resp = self.api_client.illust_detail(int(illust_id))
                illust = illust_resp.get("illust", {})
                url: Optional[str] = (
                    illust.get("meta_single_page", {}).get("original_image_url")
                    if illust.get("page_count", 1) == 1
                    else (
                        illust.get("meta_pages", [{}])[0]
                        .get("image_urls", {})
                        .get("original")
                    )
                )
                if url:
                    ext = url.split(".")[-1].split("?")[0]
                    filename = f"pixiv_{illust_id}.{ext}"
                    if path := self._download_image(url, filename):
                        self.image_paths[illust_id] = path
            except Exception as e:
                self.logger.warning(f"イラスト {illust_id} の取得に失敗: {e}")

        self.logger.info("画像ダウンロード処理が完了しました。")

    def _download_cover_image(self, novel: Dict) -> Optional[str]:
        """小説の表紙画像をダウンロードします。"""
        cover_url = novel.get("image_urls", {}).get("large")
        if not cover_url:
            self.logger.info("この小説にはカバー画像がありません。")
            return None

        def convert_url(url: str) -> str:
            return re.sub(r"/c/\d+x\d+(?:_\d+)?/", "/c/600x600/", url)

        ext = cover_url.split(".")[-1].split("?")[0]
        cover_filename = f"cover.{ext}"

        for url in (convert_url(cover_url), cover_url):
            if path := self._download_image(url, cover_filename):
                return path

        self.logger.error("カバー画像のダウンロードに最終的に失敗しました。")
        return None

    def _correct_html_image_paths(self, html_content: str) -> str:
        """
        HTMLコンテンツ内の画像パスをEPUBの構造に合わせて修正します。
        './images/' -> '../images/'
        """
        from_path = f'src="./{const.IMAGES_DIR_NAME}/'
        to_path = f'src="../{const.IMAGES_DIR_NAME}/'
        return html_content.replace(from_path, to_path)

    def _save_pages(self, novel_data: NovelApiResponse):
        """小説本文をページごとに分割し、XHTMLファイルとして保存します。"""
        text = self.parser.parse(novel_data.text)
        pages = text.split("[newpage]")
        for i, page_content in enumerate(pages):
            corrected_content = self._correct_html_image_paths(page_content)
            filename = self.paths.page_path(i + 1)
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(corrected_content)
            except IOError as e:
                self.logger.error(f"ページ {i + 1} の保存に失敗しました: {e}")
        self.logger.debug(f"{len(pages)}ページの保存が完了しました。")

    def _save_detail_json(self, novel_data: NovelApiResponse, detail_data_dict: Dict):
        """小説のメタデータを抽出し、'detail.json'として保存します。"""
        novel = detail_data_dict.get("novel", {})
        cover_path = self._download_cover_image(novel)

        text = self.parser.parse(novel_data.text)
        pages_content = text.split("[newpage]")
        pages_data = [
            {
                "title": self.parser.extract_page_title(content, i + 1),
                "body": f"./page-{i + 1}.xhtml",
            }
            for i, content in enumerate(pages_content)
        ]

        parsed_description = self.parser.parse(novel.get("caption", ""))
        corrected_description = self._correct_html_image_paths(parsed_description)

        detail_summary = {
            "title": novel.get("title"),
            "authors": {
                "name": novel.get("user", {}).get("name"),
                "id": novel.get("user", {}).get("id"),
            },
            "language": "ja",
            "series": novel.get("series"),
            "publisher": "pixiv",
            "description": corrected_description,
            "identifier": {
                "novel_id": novel.get("id"),
                "uuid": f"urn:uuid:{uuid.uuid4()}",
            },
            "date": novel.get("create_date"),
            "cover": cover_path,
            "tags": [t.get("name") for t in novel.get("tags", [])],
            "original_source": const.PIXIV_NOVEL_URL.format(novel_id=novel.get("id")),
            "pages": pages_data,
            "x_meta": {"text_length": novel.get("text_length")},
        }
        try:
            with open(self.paths.detail_json_path, "w", encoding="utf-8") as f:
                json.dump(detail_summary, f, ensure_ascii=False, indent=2)
            self.logger.debug("detail.json の保存が完了しました。")
        except IOError as e:
            self.logger.error(f"detail.json の保存に失敗しました: {e}")
