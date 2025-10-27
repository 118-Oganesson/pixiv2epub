# FILE: src/pixiv2epub/infrastructure/providers/fanbox/client.py
import time
import urllib.parse
from pathlib import Path

import cloudscraper
from loguru import logger
from pybreaker import CircuitBreaker
from requests.exceptions import RequestException

from ....shared.exceptions import ApiError, AuthenticationError
from ....shared.settings import FanboxAuthSettings
from ..base_client import BaseApiClient


class FanboxApiClient(BaseApiClient):
    """FANBOX APIと通信するためのラッパークラス。"""

    def __init__(
        self,
        breaker: CircuitBreaker,
        provider_name: str,
        auth_settings: FanboxAuthSettings,
        api_delay: float = 1.0,
        api_retries: int = 3,
    ):
        super().__init__(breaker, provider_name, api_delay, api_retries)
        sessid_value = (
            auth_settings.sessid.get_secret_value() if auth_settings.sessid else None
        )
        if not sessid_value:
            raise AuthenticationError(
                '設定に有効なFANBOXのsessidが見つかりません。', provider_name
            )

        self.base_url = auth_settings.base_url
        self.session = cloudscraper.create_scraper()
        self.session.headers.update(
            {
                'Origin': 'https://www.fanbox.cc',
                'Referer': 'https://www.fanbox.cc/',
            }
        )
        self.session.cookies.set('FANBOXSESSID', sessid_value, domain='.fanbox.cc')
        logger.debug('Fanbox APIクライアントの認証が完了しました。')

    @property
    def _api_exception_class(self) -> type[Exception]:
        return RequestException

    def _get_json(self, endpoint: str, params: dict | None = None) -> dict:
        """GETリクエストを送信し、JSONレスポンスを返します。"""
        url = self.base_url + endpoint
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # --- データ取得メソッド ---

    def creator_info(self, creator_id: str) -> dict:
        """指定されたクリエイターのプロフィール情報を取得します。"""
        return self._safe_api_call(
            self._get_json, 'creator.get', params={'creatorId': creator_id}
        )

    def post_info(self, post_id: str) -> dict:
        """指定された投稿IDの詳細な情報を取得します。"""
        return self._safe_api_call(
            self._get_json, 'post.info', params={'postId': post_id}
        )

    def post_paginate_creator(self, creator_id: str) -> dict:
        """クリエイターの投稿ページのURLリストを取得します。"""
        return self._safe_api_call(
            self._get_json, 'post.paginateCreator', params={'creatorId': creator_id}
        )

    def post_list_creator(self, url: str) -> dict:
        """ページURLから投稿リストを取得します。"""
        query_str = urllib.parse.urlparse(url).query
        params = dict(urllib.parse.parse_qsl(query_str))
        return self._safe_api_call(self._get_json, 'post.listCreator', params=params)

    def download(self, url: str, path: Path, name: str) -> None:
        """
        指定されたURLからファイルをダウンロードします。
        pixivpy3のdownloadメソッドのインターフェースに似せています。
        """
        save_path = path / name
        save_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug('ダウンロード中: {} -> {}', url, save_path)
        try:
            response = self.session.get(url, timeout=(10.0, 30.0))
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)

            # サーバー負荷軽減のための待機
            time.sleep(self.delay)

        except RequestException as e:
            logger.error('ダウンロードに失敗しました: {}, エラー: {}', url, e)
            raise ApiError(
                f'ファイルのダウンロードに失敗しました: {url}', self.provider_name
            ) from e
        except OSError as e:
            logger.error('ファイル書き込みに失敗しました: {}, エラー: {}', save_path, e)
            raise ApiError(
                f'ファイルの書き込みに失敗しました: {save_path}', self.provider_name
            ) from e
