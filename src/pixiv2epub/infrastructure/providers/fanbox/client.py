# FILE: src/pixiv2epub/infrastructure/providers/fanbox/client.py
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Type

import cloudscraper
from loguru import logger
from requests.exceptions import RequestException

from ....shared.exceptions import ApiError, AuthenticationError
from ..base_client import BaseApiClient

BASE_URL = "https://api.fanbox.cc/"


class FanboxApiClient(BaseApiClient):
    """FANBOX APIと通信するためのラッパークラス。"""

    def __init__(self, sessid: str, api_delay: float = 1.0, api_retries: int = 3):
        super().__init__(api_delay, api_retries)
        if not sessid or sessid == "your_fanbox_sessid_here":
            raise AuthenticationError(
                "設定に有効なFANBOXのsessidが見つかりません。", "fanbox"
            )

        self.session = cloudscraper.create_scraper()
        self.session.headers.update(
            {
                "Origin": "https://www.fanbox.cc",
                "Referer": "https://www.fanbox.cc/",
            }
        )
        self.session.cookies.set("FANBOXSESSID", sessid, domain=".fanbox.cc")
        logger.debug("Fanbox APIクライアントの認証が完了しました。")

    @property
    def _api_exception_class(self) -> Type[Exception]:
        return RequestException

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
            raise ApiError(
                f"ファイルのダウンロードに失敗しました: {url}", "fanbox"
            ) from e
        except IOError as e:
            logger.error(f"ファイル書き込みに失敗しました: {save_path}, エラー: {e}")
            raise ApiError(
                f"ファイルの書き込みに失敗しました: {save_path}", "fanbox"
            ) from e
