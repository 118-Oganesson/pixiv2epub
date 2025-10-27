# FILE: src/pixiv2epub/infrastructure/providers/fanbox/auth.py
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright

from ....shared.exceptions import AuthenticationError


async def get_fanbox_sessid(save_session_path: Path) -> str:
    """
    ブラウザを起動してユーザーにFANBOXへログインさせ、FANBOXSESSIDクッキーを取得します。

    Args:
        save_session_path (Path): ブラウザセッションを保存するパス。

    Returns:
        str: 取得したFANBOXSESSID。

    Raises:
        AuthenticationError: FANBOXSESSIDクッキーの取得に失敗した場合。
    """
    async with async_playwright() as p:
        # 保存されたセッションを使ってブラウザを起動
        context = await p.chromium.launch_persistent_context(
            save_session_path, headless=False
        )
        page = context.pages[0] if context.pages else await context.new_page()

        logger.info(
            "FANBOXのサイトを開きます... もしログインしていない場合は、ログインしてください。"
        )
        await page.goto("https://www.fanbox.cc/")

        # ユーザーに手動でのログインを促す
        input(
            "ブラウザでFANBOXにログインした後、このコンソールに戻りEnterキーを押してください..."
        )

        logger.info("クッキーを取得しています...")
        cookies = await context.cookies()
        fanbox_sessid: str | None = None
        for cookie in cookies:
            if cookie["name"] == "FANBOXSESSID":
                fanbox_sessid = cookie["value"]
                break

        await context.close()

        if fanbox_sessid:
            logger.info("✅ FANBOXSESSIDの取得に成功しました！")
            return fanbox_sessid
        else:
            raise AuthenticationError(
                "FANBOXSESSIDが見つかりませんでした。正常にログインできているか確認してください。"
            )
