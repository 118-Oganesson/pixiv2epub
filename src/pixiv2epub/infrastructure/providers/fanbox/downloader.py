# FILE: src/pixiv2epub/infrastructure/providers/fanbox/downloader.py

from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from ....models.fanbox import Post
from .client import FanboxApiClient


class FanboxImageDownloader:
    """
    Fanboxの投稿に関連する画像をダウンロードする責務を持つクラス。
    """

    def __init__(
        self,
        api_client: FanboxApiClient,
        image_dir: Path,
        overwrite: bool,
    ):
        """
        Args:
            api_client (FanboxApiClient): Fanbox APIと通信するためのクライアント。
            image_dir (Path): 画像の保存先ディレクトリ。
            overwrite (bool): 既存の画像を上書きするかどうか。
        """
        self.api_client = api_client
        self.image_dir = image_dir
        self.overwrite = overwrite

    def _download_single_image(self, url: str, filename: str) -> Optional[Path]:
        """単一の画像をダウンロードし、ローカルパスを返します。"""
        target_path = self.image_dir / filename
        if target_path.exists() and not self.overwrite:
            logger.debug(f"画像は既に存在するためスキップ: {filename}")
            return target_path

        try:
            self.api_client.download(url, path=self.image_dir, name=filename)
            logger.debug(f"画像をダウンロードしました: {filename}")
            return target_path
        except Exception as e:
            logger.warning(f"画像 ({url}) のダウンロードに失敗しました: {e}")
            return None

    def download_cover(self, post_data: Post) -> Optional[Path]:
        """投稿のカバー画像をダウンロードします。"""
        if not post_data.cover_image_url:
            logger.info("この投稿にはカバー画像がありません。")
            return None

        cover_url = str(post_data.cover_image_url)
        ext = cover_url.split(".")[-1].split("?")[0]  # URLから拡張子を安全に取得
        cover_filename = f"cover.{ext}"

        logger.info(f"カバー画像をダウンロードします: {cover_filename}")
        return self._download_single_image(cover_url, cover_filename)

    def download_embedded_images(self, post_data: Post) -> Dict[str, Path]:
        """本文中のすべての画像をダウンロードし、IDとパスのマッピングを返します。"""
        image_paths: Dict[str, Path] = {}
        if not hasattr(post_data.body, "image_map") or not post_data.body.image_map:
            logger.info("本文中に埋め込み画像はありません。")
            return image_paths

        total_images = len(post_data.body.image_map)
        logger.info(f"{total_images}件の埋め込み画像をダウンロードします。")

        for image_id, image_item in post_data.body.image_map.items():
            url = str(image_item.original_url)
            filename = f"{image_id}.{image_item.extension}"
            if path := self._download_single_image(url, filename):
                image_paths[image_id] = path

        logger.info("埋め込み画像のダウンロード処理が完了しました。")
        return image_paths
