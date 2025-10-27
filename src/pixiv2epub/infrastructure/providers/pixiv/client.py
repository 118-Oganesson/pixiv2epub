# FILE: src/pixiv2epub/infrastructure/providers/pixiv/client.py
from pathlib import Path

from loguru import logger
from pixivpy3 import AppPixivAPI, PixivError
from pybreaker import CircuitBreaker

from ....shared.exceptions import AuthenticationError
from ....shared.settings import PixivAuthSettings
from ..base_client import BaseApiClient


class PixivApiClient(BaseApiClient):
    """Pixiv APIと通信するためのラッパークラス。"""

    def __init__(
        self,
        breaker: CircuitBreaker,
        provider_name: str,
        auth_settings: PixivAuthSettings,
        api_delay: float = 1.0,
        api_retries: int = 3,
    ):
        super().__init__(breaker, provider_name, api_delay, api_retries)
        token_value = (
            auth_settings.refresh_token.get_secret_value()
            if auth_settings.refresh_token
            else None
        )
        if not token_value:
            raise AuthenticationError(
                '設定に有効なPixivのrefresh_tokenが見つかりません。', provider_name
            )

        self.api = AppPixivAPI()
        try:
            self.api.auth(refresh_token=token_value)
            logger.debug('Pixiv APIの認証が完了しました。')
        except PixivError as e:
            raise AuthenticationError(
                f'Pixiv APIの認証に失敗しました: {e}', provider_name
            ) from e

    @property
    def _api_exception_class(self) -> type[Exception]:
        return PixivError

    def novel_detail(self, novel_id: int) -> dict:
        return self._safe_api_call(self.api.novel_detail, novel_id=novel_id)

    def webview_novel(self, novel_id: int) -> dict:
        return self._safe_api_call(self.api.webview_novel, novel_id=novel_id)

    def novel_series(self, series_id: int) -> dict:
        return self._safe_api_call(self.api.novel_series, series_id=series_id)

    def illust_detail(self, illust_id: int) -> dict:
        return self._safe_api_call(self.api.illust_detail, illust_id=illust_id)

    def user_novels(self, user_id: int, next_url: str | None = None) -> dict:
        if next_url:
            params = self.api.parse_qs(next_url)
            return self._safe_api_call(self.api.user_novels, **params)
        return self._safe_api_call(self.api.user_novels, user_id=user_id)

    def download(self, url: str, path: Path, name: str) -> None:
        return self._safe_api_call(self.api.download, url, path=path, name=name)
