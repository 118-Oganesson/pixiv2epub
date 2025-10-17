# FILE: src/pixiv2epub/infrastructure/providers/pixiv/constants.py

PIXIV_NOVEL_URL = "https://www.pixiv.net/novel/show.php?id={novel_id}"
PIXIV_ARTWORK_URL = "https://www.pixiv.net/artworks/{illust_id}"

# 認証関連の定数
USER_AGENT = "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
