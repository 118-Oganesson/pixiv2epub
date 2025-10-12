# FILE: src/pixiv2epub/infrastructure/providers/fanbox/client.py

import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import cloudscraper
from loguru import logger
from requests.exceptions import RequestException

from ....shared.exceptions import AuthenticationError, DownloadError

# APIのベースURL
BASE_URL = "https://api.fanbox.cc/"


class FanboxApiClient:
    """FANBOX APIと通信するためのラッパークラス。"""

    def __init__(self, sessid: str, api_delay: float = 1.0, api_retries: int = 3):
        if not sessid or sessid == "your_fanbox_sessid_here":
            raise AuthenticationError("設定に有効なFANBOXのsessidが見つかりません。")

        self.delay = api_delay
        self.retry = api_retries
        self.session = cloudscraper.create_scraper()
        self.session.headers.update(
            {
                "Origin": "https://www.fanbox.cc",
                "Referer": "https://www.fanbox.cc/",
            }
        )
        self.session.cookies.set("FANBOXSESSID", sessid, domain=".fanbox.cc")
        logger.debug("Fanbox APIクライアントの認証が完了しました。")

    def _safe_api_call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """API呼び出しをリトライ機構付きで安全に実行します。"""
        for attempt in range(1, self.retry + 1):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.delay)
                return result
            except RequestException as e:
                status_code = getattr(e.response, "status_code", None)

                # 認証エラー (401, 403など) は AuthenticationError にラップ
                if status_code in [401, 403]:
                    raise AuthenticationError(
                        f"Fanbox API認証エラー (HTTP {status_code})"
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
                    f"API '{func.__name__}' 呼び出し中にエラー (試行 {attempt}/{self.retry + 1}): {e} (HTTP: {status_code or 'N/A'})"
                )
                if attempt > self.retry:
                    logger.error(f"API呼び出しが最終的に失敗しました: {func.__name__}")
                    raise DownloadError(
                        f"API呼び出しがリトライ上限に達しました: {func.__name__}"
                    ) from e
                time.sleep(self.delay * attempt)
        raise RuntimeError("API呼び出しがリトライ回数を超えました。")

    def _get_json(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """GETリクエストを送信し、JSONレスポンスを返します。"""
        url = BASE_URL + endpoint
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # --- データ取得メソッド ---

    def creator_info(self, creator_id: str) -> Dict:
        """指定されたクリエイターのプロフィール情報を取得します。"""
        return self._safe_api_call(
            self._get_json, "creator.get", params={"creatorId": creator_id}
        )

    def post_info(self, post_id: str) -> Dict:
        """指定された投稿IDの詳細な情報を取得します。"""
        return self._safe_api_call(
            self._get_json, "post.info", params={"postId": post_id}
        )

    def post_paginate_creator(self, creator_id: str) -> Dict:
        """クリエイターの投稿ページのURLリストを取得します。"""
        return self._safe_api_call(
            self._get_json, "post.paginateCreator", params={"creatorId": creator_id}
        )

    def post_list_creator(self, url: str) -> Dict:
        """ページURLから投稿リストを取得します。"""
        query_str = urllib.parse.urlparse(url).query
        params = dict(urllib.parse.parse_qsl(query_str))
        return self._safe_api_call(self._get_json, "post.listCreator", params=params)

    def download(self, url: str, path: Path, name: str) -> None:
        """
        指定されたURLからファイルをダウンロードします。
        pixivpy3のdownloadメソッドのインターフェースに似せています。
        """
        save_path = path / name
        save_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"ダウンロード中: {url} -> {save_path}")
        try:
            response = self.session.get(url, timeout=(10.0, 30.0))
            response.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(response.content)

            # サーバー負荷軽減のための待機
            time.sleep(self.delay)

        except RequestException as e:
            logger.error(f"ダウンロードに失敗しました: {url}, エラー: {e}")
            raise DownloadError(f"ファイルのダウンロードに失敗しました: {url}") from e
        except IOError as e:
            logger.error(f"ファイル書き込みに失敗しました: {save_path}, エラー: {e}")
            raise DownloadError(f"ファイルの書き込みに失敗しました: {save_path}") from e
