# FILE: src/pixiv2epub/infrastructure/providers/fanbox/fetcher.py
from typing import Any

from ....models.domain import FetchedData
from .client import FanboxApiClient


class FanboxFetcher:
    """Fanbox APIから生データを取得する責務を持つクラス。"""

    def __init__(self, api_client: FanboxApiClient):
        self.api_client = api_client

    def fetch_novel_data(self, content_id: Any) -> FetchedData:
        """指定された投稿IDの詳細な情報を取得し、FetchedDataに格納して返します。"""
        post_data = self.api_client.post_info(content_id)
        return FetchedData(primary_data=post_data)
