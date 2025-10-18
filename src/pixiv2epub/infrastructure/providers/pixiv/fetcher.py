# FILE: src/pixiv2epub/infrastructure/providers/pixiv/fetcher.py
from typing import Dict, Tuple

from .client import PixivApiClient


class PixivFetcher:
    """Pixiv APIから生データを取得する責務を持つクラス。"""

    def __init__(self, api_client: PixivApiClient):
        self.api_client = api_client

    def fetch_novel_data(self, work_id: int) -> Tuple[Dict, Dict]:
        """小説の処理に必要なWebviewと詳細データを両方取得します。"""
        raw_webview_novel_data = self.api_client.webview_novel(work_id)
        raw_novel_detail_data = self.api_client.novel_detail(work_id)
        return raw_webview_novel_data, raw_novel_detail_data
