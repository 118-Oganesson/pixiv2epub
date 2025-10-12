# FILE: src/pixiv2epub/infrastructure/providers/pixiv/client.py
import time
from pathlib import Path
from typing import Any, Callable, Dict

from loguru import logger
from pixivpy3 import AppPixivAPI, PixivError

from ....shared.exceptions import AuthenticationError, DownloadError


class PixivApiClient:
    """Pixiv APIと通信するためのラッパークラス。"""

    def __init__(
        self, refresh_token: str, api_delay: float = 1.0, api_retries: int = 3
    ):
        self.delay = api_delay
        self.retry = api_retries

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

    def _safe_api_call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """API呼び出しをリトライ機構付きで安全に実行します。"""
        for attempt in range(1, self.retry + 1):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.delay)
                return result
            except PixivError as e:
                status_code = getattr(getattr(e, "response", None), "status_code", None)

                # 認証エラー (401, 403など) は AuthenticationError にラップ
                if status_code in [401, 403]:
                    raise AuthenticationError(
                        f"Pixiv API認証エラー (HTTP {status_code})"
                    ) from e

                # 4xx系のクライアントエラーはリトライせず、DownloadErrorにラップ
                if status_code and 400 <= status_code < 500:
                    logger.error(
                        f"API '{func.__name__}' で回復不能なクライアントエラー (HTTP {status_code})"
                    )
                    raise DownloadError(
                        f"APIクライアントエラー (HTTP {status_code})"
                    ) from e

                logger.warning(
                    f"API '{func.__name__}' 呼び出し中にエラー (試行 {attempt}/{self.retry}): {e} (HTTP: {status_code or 'N/A'})"
                )
                if attempt == self.retry:
                    logger.error(f"API呼び出しが最終的に失敗しました: {func.__name__}")
                    raise DownloadError(
                        f"API呼び出しがリトライ上限に達しました: {func.__name__}"
                    ) from e
                time.sleep(self.delay * attempt)
        raise RuntimeError("API呼び出しがリトライ回数を超えました。")

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
