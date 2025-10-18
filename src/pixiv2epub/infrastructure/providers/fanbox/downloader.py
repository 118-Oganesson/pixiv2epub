# FILE: src/pixiv2epub/infrastructure/providers/fanbox/downloader.py
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from ....models.fanbox import Post
from ..base_downloader import BaseDownloader
from .client import FanboxApiClient
from ....shared.constants import COVER_IMAGE_STEM


class FanboxImageDownloader(BaseDownloader):
    """
    Fanboxの投稿に関連する画像をダウンロードする責務を持つクラス。
    """

    def __init__(
        self,
        api_client: FanboxApiClient,
        overwrite: bool,
    ):
        """
        Args:
            api_client (FanboxApiClient): Fanbox APIと通信するためのクライアント。
            overwrite (bool): 既存の画像を上書きするかどうか。
        """
        super().__init__(api_client, overwrite)

    def download_cover(
        self,
        post_data: Post,
        image_dir: Path,
    ) -> Optional[Path]:
        """投稿のカバー画像をダウンロードします。"""
        if not post_data.cover_image_url:
            logger.info("この投稿にはカバー画像がありません。")
            return None

        cover_url = str(post_data.cover_image_url)
        ext = cover_url.split(".")[-1].split("?")[0]  # URLから拡張子を安全に取得
        cover_filename = f"{COVER_IMAGE_STEM}.{ext}"

        logger.info("カバー画像をダウンロードします。")
        return self._download_single_image(cover_url, cover_filename, image_dir)

    def download_embedded_images(
        self,
        post_data: Post,
        image_dir: Path,
    ) -> Dict[str, Path]:
        """本文中のすべての画像をダウンロードし、IDとパスのマッピングを返します。"""
        image_paths: Dict[str, Path] = {}
        if not hasattr(post_data.body, "image_map") or not post_data.body.image_map:
            logger.info("本文中に埋め込み画像はありません。")
            return image_paths

        total_images = len(post_data.body.image_map)
        logger.info("{}件の埋め込み画像をダウンロードします。", total_images)

        for image_id, image_item in post_data.body.image_map.items():
            url = str(image_item.original_url)
            filename = f"{image_id}.{image_item.extension}"
            if path := self._download_single_image(url, filename, image_dir):
                image_paths[image_id] = path

        logger.info("埋め込み画像のダウンロード処理が完了しました。")
        return image_paths
