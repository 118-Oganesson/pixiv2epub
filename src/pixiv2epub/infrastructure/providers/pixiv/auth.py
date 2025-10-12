# FILE: src/pixiv2epub/infrastructure/providers/pixiv/auth.py
import re
import time
from base64 import urlsafe_b64encode
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from typing import Tuple
from urllib.parse import urlencode

import requests
from loguru import logger
from playwright.sync_api import Request, TimeoutError, sync_playwright

from ....shared.exceptions import AuthenticationError

# ----- 定数 -----
USER_AGENT = "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"


def _s256(data: bytes) -> str:
    """SHA256ハッシュを計算し、Base64URLエンコードする"""
    return urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")


def _oauth_pkce() -> Tuple[str, str]:
    """PKCE用の code_verifier と code_challenge を生成する"""
    code_verifier = token_urlsafe(32)
    code_challenge = _s256(code_verifier.encode("ascii"))
    return code_verifier, code_challenge


def _login_and_get_code(save_session_path: Path) -> Tuple[str, str]:
    """Playwright を使用してブラウザでログインし、認可コードを取得する"""
    code_verifier, code_challenge = _oauth_pkce()
    login_params = {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }
    logger.debug(f"Code verifier: {code_verifier}")

    auth_code_holder = []

    def handle_request(request: Request):
        if request.url.startswith("pixiv://"):
            logger.info(f"コールバックURLを検出: {request.url}")
            match = re.search(r"code=([^&]*)", request.url)
            if match and not auth_code_holder:
                auth_code_holder.append(match.groups()[0])

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            save_session_path, headless=False
        )
        page = context.new_page()
        logger.info(
            "ブラウザを起動しました。表示されたウィンドウでPixivにログインしてください..."
        )

        page.on("request", handle_request)
        login_page_url = f"{LOGIN_URL}?{urlencode(login_params)}"
        page.goto(login_page_url)

        try:
            logger.info("ブラウザでのログイン操作を待機しています...")
            start_time = time.time()
            while not auth_code_holder:
                page.wait_for_timeout(500)
                if time.time() - start_time > 300:
                    raise TimeoutError("ログイン操作が5分以内に完了されませんでした。")

            logger.info("認可コードの取得に成功しました。")
            time.sleep(2)

        except Exception as e:
            raise AuthenticationError(
                f"ログインプロセスがタイムアウトしたか、失敗しました: {e}"
            )
        finally:
            context.close()
            logger.info("ブラウザを終了しました。")

    if not auth_code_holder:
        raise AuthenticationError(
            "認可コードを取得できませんでした。ログインが完了していない可能性があります。"
        )

    code = auth_code_holder[0]
    logger.debug(f"Auth code: {code}")
    return code, code_verifier


def _get_refresh_token(code: str, code_verifier: str) -> str:
    """認可コードを使用してリフレッシュトークンを取得する"""
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "include_policy": "true",
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"User-Agent": USER_AGENT, "App-OS-Version": "14.6", "App-OS": "ios"}
    response = requests.post(AUTH_TOKEN_URL, data=data, headers=headers)

    response_data = response.json()
    if "refresh_token" not in response_data:
        raise AuthenticationError(
            f"リフレッシュトークンの取得に失敗しました。APIからの応答: {response_data}"
        )

    refresh_token = response_data["refresh_token"]
    logger.info("リフレッシュトークンの取得に成功しました。")
    return refresh_token


def get_pixiv_refresh_token(save_session_path: Path) -> str:
    """
    一連の認証フローを実行し、Pixivのリフレッシュトークンを取得する。
    """
    try:
        auth_code, verifier = _login_and_get_code(save_session_path)
        refresh_token = _get_refresh_token(auth_code, verifier)
        return refresh_token
    except Exception as e:
        logger.error(f"認証中に予期せぬエラーが発生しました: {e}")
        raise
