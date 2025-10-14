# FILE: src/pixiv2epub/shared/exceptions.py


class Pixiv2EpubError(Exception):
    """アプリケーションの基底例外クラス。"""

    pass


class SettingsError(Pixiv2EpubError):
    """設定関連のエラー。"""

    pass


class InvalidInputError(Pixiv2EpubError):
    """不正なURLやIDが入力された場合のエラー。"""

    pass


class ProviderError(Pixiv2EpubError):
    """データプロバイダー層で発生したエラーの基底クラス。"""

    def __init__(self, message: str, provider_name: str | None = None):
        if provider_name:
            super().__init__(f"[{provider_name}] {message}")
        else:
            super().__init__(message)
        self.provider_name = provider_name


class AuthenticationError(ProviderError):
    """認証に関するエラー。"""

    pass


class ContentNotFoundError(ProviderError):
    """要求されたコンテンツが見つからないエラー。"""

    pass


class ApiError(ProviderError):
    """API通信中の回復可能な可能性のあるエラー（タイムアウト、5xxエラーなど）。"""

    pass


class DataProcessingError(Pixiv2EpubError):
    """ダウンロード後のデータ処理中のエラー（パース、マッピングなど）。"""

    pass


class BuildError(Pixiv2EpubError):
    """ビルド処理中のエラーの基底クラス。"""

    pass


class AssetMissingError(BuildError):
    """ビルドに必要なアセット（manifest.jsonなど）が見つからないエラー。"""

    pass


class TemplateError(BuildError):
    """テンプレートのレンダリング中に発生したエラー。"""

    pass
