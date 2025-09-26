# src/pixiv2epub/providers/pixiv/downloader.py

import logging
import re
from pathlib import Path
from typing import Dict, Optional

from ...models.pixiv import NovelApiResponse
from .client import PixivApiClient


class ImageDownloader:
    """
    小説に関連する画像をダウンロードする責務を持つクラス。
    ネットワークI/Oに特化します。
    """

    def __init__(
        self,
        api_client: PixivApiClient,
        image_dir: Path,
        overwrite: bool,
    ):
        """
        Args:
            api_client (PixivApiClient): Pixiv APIと通信するためのクライアント。
            image_dir (Path): 画像の保存先ディレクトリ。
            overwrite (bool): 既存の画像を上書きするかどうか。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.api_client = api_client
        self.image_dir = image_dir
        self.overwrite = overwrite

    def _download_single_image(self, url: str, filename: str) -> Optional[Path]:
        """単一の画像をダウンロードし、ローカルパスを返します。"""
        target_path = self.image_dir / filename
        if target_path.exists() and not self.overwrite:
            self.logger.debug(f"画像は既に存在するためスキップ: {filename}")
            return target_path

        try:
            self.api_client.download(url, path=self.image_dir, name=filename)
            self.logger.debug(f"画像をダウンロードしました: {filename}")
            return target_path
        except Exception as e:
            self.logger.warning(f"画像 ({url}) のダウンロードに失敗しました: {e}")
            return None

    def download_cover(self, novel_detail: dict) -> Optional[Path]:
        """小説の表紙画像をダウンロードします。"""
        cover_url = novel_detail.get("image_urls", {}).get("large")
        if not cover_url:
            self.logger.info("この小説にはカバー画像がありません。")
            return None

        def convert_url(url: str) -> str:
            return re.sub(r"/c/\d+x\d+(?:_\d+)?/", "/c/600x600/", url)

        ext = cover_url.split(".")[-1].split("?")[0]
        cover_filename = f"cover.{ext}"

        # 高解像度版、オリジナル版の順で試行
        for url in (convert_url(cover_url), cover_url):
            if path := self._download_single_image(url, cover_filename):
                return path

        self.logger.error("カバー画像のダウンロードに最終的に失敗しました。")
        return None

    def download_embedded_images(self, novel_data: NovelApiResponse) -> Dict[str, Path]:
        """本文中のすべての画像をダウンロードし、IDとパスのマッピングを返します。"""
        self.logger.info("埋め込み画像のダウンロードを開始します...")
        text = novel_data.text
        uploaded_ids = set(re.findall(r"\[uploadedimage:(\d+)\]", text))
        pixiv_ids = set(re.findall(r"\[pixivimage:(\d+)\]", text))

        total_images = len(uploaded_ids) + len(pixiv_ids)
        self.logger.info(f"対象画像: {total_images}件")

        image_paths: Dict[str, Path] = {}

        for image_id in uploaded_ids:
            image_meta = novel_data.images.get(image_id)
            if image_meta and image_meta.urls.original:
                url = image_meta.urls.original
                ext = url.split(".")[-1].split("?")[0]
                filename = f"uploaded_{image_id}.{ext}"
                if path := self._download_single_image(url, filename):
                    image_paths[image_id] = path

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
                    if path := self._download_single_image(url, filename):
                        image_paths[illust_id] = path
            except Exception as e:
                self.logger.warning(f"イラスト {illust_id} の取得に失敗: {e}")

        self.logger.info("埋め込み画像ダウンロード処理が完了しました。")
        return image_paths
