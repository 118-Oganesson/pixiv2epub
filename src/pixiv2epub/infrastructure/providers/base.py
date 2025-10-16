# FILE: src/pixiv2epub/infrastructure/providers/base.py
from typing import Any, List, Protocol, runtime_checkable

from loguru import logger

from ...models.workspace import Workspace
from ...shared.settings import Settings


@runtime_checkable
class IProvider(Protocol):
    """データソースプロバイダの振る舞いを定義するプロトコル。"""

    settings: Settings

    def __init__(self, settings: Settings):
        """
        プロバイダの初期化。

        Args:
            settings (Settings): アプリケーション全体の設定情報。
        """
        self.settings = settings
        logger.info(f"{self.__class__.__name__} を初期化しました。")

    @classmethod
    def get_provider_name(cls) -> str:
        """プロバイダの名前を返すクラスメソッド。"""
        ...


@runtime_checkable
class IWorkProvider(Protocol):
    """単一の作品を取得するためのインターフェース"""

    def get_work(self, work_id: Any) -> Workspace:
        """単一の作品を取得し、Workspaceを生成して返します。"""
        ...


@runtime_checkable
class IMultiWorkProvider(Protocol):
    """作品群を取得するためのインターフェース"""

    def get_multiple_works(self, collection_id: Any) -> List[Workspace]:
        """コレクション（シリーズなど）に含まれるすべての作品を取得し、Workspaceのリストを返します。"""
        ...


@runtime_checkable
class ICreatorProvider(Protocol):
    """クリエイターの全作品を取得するためのインターフェース"""

    def get_creator_works(self, creator_id: Any) -> List[Workspace]:
        """特定のクリエイターが投稿したすべての作品を取得し、Workspaceのリストを返します。"""
        ...
