# FILE: src/pixiv2epub/infrastructure/providers/base_provider.py
from loguru import logger
from pybreaker import CircuitBreaker

from ...domain.interfaces import IProvider
from ...shared.settings import Settings


class BaseProvider(IProvider):
    """プロバイダーの共通的な振る舞いを定義する抽象基底クラス。"""

    def __init__(self, settings: Settings, breaker: CircuitBreaker):
        """
        Args:
            settings (Settings): アプリケーション設定。
            breaker (CircuitBreaker): 共有サーキットブレーカーインスタンス。
        """
        self.settings = settings
        self.workspace_dir = settings.workspace.root_directory
        self._breaker: CircuitBreaker = breaker

        logger.bind(provider_name=self.__class__.__name__).info(
            "プロバイダーを初期化しました。"
        )

    @property
    def breaker(self) -> CircuitBreaker:
        """サーキットブレーカーのインスタンスを返します。"""
        return self._breaker
