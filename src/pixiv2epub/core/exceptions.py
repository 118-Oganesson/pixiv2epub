# FILE: src/pixiv2epub/core/exceptions.py


class Pixiv2EpubError(Exception):
    """アプリケーションの基底例外クラス。"""

    pass


class SettingsError(Pixiv2EpubError):
    """設定関連のエラー。"""

    pass


class AuthenticationError(Pixiv2EpubError):
    """認証に関するエラー。"""

    pass


class DownloadError(Pixiv2EpubError):
    """ダウンロード処理中のエラー。"""

    pass


class BuildError(Pixiv2EpubError):
    """ビルド処理中のエラー。"""

    pass


class InvalidInputError(Pixiv2EpubError):
    """不正なURLやIDが入力された場合のエラー。"""

    pass
