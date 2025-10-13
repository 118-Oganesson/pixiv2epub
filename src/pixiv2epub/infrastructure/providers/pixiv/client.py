# FILE: src/pixiv2epub/infrastructure/providers/pixiv/client.py
from pathlib import Path
from typing import Dict, Type

from loguru import logger
from pixivpy3 import AppPixivAPI, PixivError

from ....shared.exceptions import AuthenticationError
from ..base_client import BaseApiClient


class PixivApiClient(BaseApiClient):
    """Pixiv APIと通信するためのラッパークラス。"""

    def __init__(
        self, refresh_token: str, api_delay: float = 1.0, api_retries: int = 3
    ):
        super().__init__(api_delay, api_retries)
        if not refresh_token or refresh_token == "your_refresh_token_here":
            raise AuthenticationError(
                "設定に有効なPixivのrefresh_tokenが見つかりません。"
            )

        self.api = AppPixivAPI()
        try:
            self.api.auth(refresh_token=refresh_token)
            logger.debug("Pixiv APIの認証が完了しました。")
        except PixivError as e:
            raise AuthenticationError(f"Pixiv APIの認証に失敗しました: {e}")

    @property
    def _api_exception_class(self) -> Type[Exception]:
        return PixivError

    def novel_detail(self, novel_id: int) -> Dict:
        return self._safe_api_call(self.api.novel_detail, novel_id)

    def webview_novel(self, novel_id: int) -> Dict:
        return self._safe_api_call(self.api.webview_novel, novel_id)

    def novel_series(self, series_id: int) -> Dict:
        return self._safe_api_call(self.api.novel_series, series_id=series_id)

    def illust_detail(self, illust_id: int) -> Dict:
        return self._safe_api_call(self.api.illust_detail, illust_id)

    def user_novels(self, user_id: int, next_url: str = None) -> Dict:
        if next_url:
            params = self.api.parse_qs(next_url)
            return self._safe_api_call(self.api.user_novels, **params)
        return self._safe_api_call(self.api.user_novels, user_id=user_id)

    def download(self, url: str, path: Path, name: str) -> None:
        return self._safe_api_call(self.api.download, url, path=path, name=name)
