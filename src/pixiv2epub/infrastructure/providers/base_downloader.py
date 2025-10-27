# FILE: src/pixiv2epub/infrastructure/providers/base_downloader.py
from pathlib import Path
from typing import Protocol

from loguru import logger


class Downloadable(Protocol):
    """
    downloadメソッドを持つAPIクライアントの振る舞いを定義するプロトコル。
    """

    def download(self, url: str, path: Path, name: str) -> None: ...


class BaseDownloader:
    """
    画像ダウンロードの共通ロジックをカプセル化する基底クラス。
    """

    def __init__(self, api_client: Downloadable, overwrite: bool):
        self.api_client = api_client
        self.overwrite = overwrite

    def _download_single_image(
        self,
        url: str,
        filename: str,
        image_dir: Path,
    ) -> Path | None:
        """単一の画像をダウンロードし、ローカルパスを返します。"""
        target_path = image_dir / filename
        if target_path.exists() and not self.overwrite:
            logger.debug("画像は既に存在するためスキップ: {}", filename)
            return target_path

        try:
            self.api_client.download(url, path=image_dir, name=filename)
            logger.debug("画像をダウンロードしました: {}", filename)
            return target_path
        except Exception as e:
            logger.warning("画像 ({}) のダウンロードに失敗しました: {}", url, e)
            return None
