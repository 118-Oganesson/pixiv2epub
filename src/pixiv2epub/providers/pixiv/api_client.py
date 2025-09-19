#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/providers/pixiv/api_client.py
#
# Pixiv APIとの通信を担当するクライアント。
# 認証、API呼び出しのリトライ、エラーハンドリングなど、
# 通信に関する低レベルな処理をカプセル化します。
# -----------------------------------------------------------------------------

import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict

from pixivpy3 import AppPixivAPI, PixivError


class PixivApiClient:
    """Pixiv APIと通信するためのラッパークラス。"""

    def __init__(
        self, refresh_token: str, api_delay: float = 1.0, api_retries: int = 3
    ):
        """
        PixivApiClientを初期化し、API認証を行います。

        Args:
            refresh_token (str): Pixivのリフレッシュトークン。
            api_delay (float): 各API呼び出し後の遅延時間（秒）。
            api_retries (int): API呼び出し失敗時のリトライ回数。

        Raises:
            ValueError: リフレッシュトークンが無効な場合。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.delay = api_delay
        self.retry = api_retries

        if not refresh_token or refresh_token == "your_refresh_token_here":
            raise ValueError("設定に有効なPixivのrefresh_tokenが見つかりません。")

        self.api = AppPixivAPI()
        self.api.auth(refresh_token=refresh_token)
        self.logger.debug("Pixiv APIの認証が完了しました。")

    def _safe_api_call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """API呼び出しをリトライ機構付きで安全に実行します。"""
        for attempt in range(1, self.retry + 1):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.delay)
                return result
            except PixivError as e:
                self.logger.warning(
                    f"API '{func.__name__}' 呼び出し中にエラー (試行 {attempt}/{self.retry}): {e}"
                )
                if attempt == self.retry:
                    self.logger.error(
                        f"API呼び出しが最終的に失敗しました: {func.__name__}"
                    )
                    raise
                time.sleep(self.delay * attempt)
        raise RuntimeError("API呼び出しがリトライ回数を超えました。")

    def novel_detail(self, novel_id: int) -> Dict:
        """小説の詳細データを取得します。"""
        return self._safe_api_call(self.api.novel_detail, novel_id)

    def webview_novel(self, novel_id: int) -> Dict:
        """小説の本文を含むWebView用のデータを取得します。"""
        return self._safe_api_call(self.api.webview_novel, novel_id)

    def novel_series(self, series_id: int) -> Dict:
        """シリーズの詳細データを取得します。"""
        return self._safe_api_call(self.api.novel_series, series_id=series_id)

    def illust_detail(self, illust_id: int) -> Dict:
        """イラストの詳細データを取得します。"""
        return self._safe_api_call(self.api.illust_detail, illust_id)

    def user_novels(self, user_id: int, next_url: str = None) -> Dict:
        """ユーザーの投稿小説リストを取得します。ページネーションにも対応します。"""
        if next_url:
            params = self.api.parse_qs(next_url)
            return self._safe_api_call(self.api.user_novels, **params)
        return self._safe_api_call(self.api.user_novels, user_id=user_id)

    def download(self, url: str, path: Path, name: str) -> None:
        """指定されたURLからファイルをダウンロードします。"""
        return self._safe_api_call(self.api.download, url, path=path, name=name)
