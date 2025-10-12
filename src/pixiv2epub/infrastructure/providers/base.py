# FILE: src/pixiv2epub/infrastructure/providers/base.py
from abc import ABC, abstractmethod
from typing import Any, List

from loguru import logger

from ...models.workspace import Workspace
from ...shared.settings import Settings


class IProvider(ABC):
    """データソースプロバイダの抽象基底クラス。"""

    def __init__(self, settings: Settings):
        """
        プロバイダの初期化。

        Args:
            settings (Settings): アプリケーション全体の設定情報。
        """
        self.settings = settings
        logger.info(f"{self.__class__.__name__} を初期化しました。")

    @classmethod
    @abstractmethod
    def get_provider_name(cls) -> str:
        """プロバイダの名前を返すクラスメソッド。"""
        pass


class INovelProvider(ABC):
    """単一の小説を取得するためのインターフェース"""

    @abstractmethod
    def get_novel(self, novel_id: Any) -> Workspace:
        """単一の小説を取得し、Workspaceを生成して返します。"""
        pass


class ISeriesProvider(ABC):
    """シリーズ作品を取得するためのインターフェ-ス"""

    @abstractmethod
    def get_series(self, series_id: Any) -> List[Workspace]:
        """シリーズに含まれるすべての小説を取得し、Workspaceのリストを返します。"""
        pass


class IUserNovelsProvider(ABC):
    """ユーザーの全作品を取得するためのインターフェース"""

    @abstractmethod
    def get_user_novels(self, user_id: Any) -> List[Workspace]:
        """特定のユーザーが投稿したすべての小説を取得し、Workspaceのリストを返します。"""
        pass
