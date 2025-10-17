# FILE: src/pixiv2epub/infrastructure/providers/pixiv/constants.py

# Pixivの作品URLを生成するためのフォーマット文字列
PIXIV_NOVEL_URL = "https://www.pixiv.net/novel/show.php?id={novel_id}"
PIXIV_ARTWORK_URL = "https://www.pixiv.net/artworks/{illust_id}"

# --- 認証関連の定数 ---
# APIリクエスト時に使用するユーザーエージェント文字列
USER_AGENT = "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)"
# ログインページのURL
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
# 認証トークンを取得するためのエンドポイントURL
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
# Pixiv APIの公開クライアントID
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
# Pixiv APIの公開クライアントシークレット
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
# OAuth認証フローで使用されるリダイレクトURI
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
