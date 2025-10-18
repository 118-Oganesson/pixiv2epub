# FILE: src/pixiv2epub/infrastructure/providers/fanbox/fetcher.py
from typing import Any, Dict

from .client import FanboxApiClient


class FanboxFetcher:
    """Fanbox APIから生データを取得する責務を持つクラス。"""

    def __init__(self, api_client: FanboxApiClient):
        self.api_client = api_client

    def fetch_post_data(self, post_id: Any) -> Dict:
        """指定された投稿IDの詳細な情報を取得します。"""
        return self.api_client.post_info(post_id)
