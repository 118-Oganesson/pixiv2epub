# FILE: src/pixiv2epub/domain/interfaces.py
from pathlib import Path
from typing import Any, List, Protocol, runtime_checkable

from ..models.workspace import Workspace
from ..shared.settings import Settings


class IBuilder(Protocol):
    """成果物をビルドするためのインターフェース。"""

    def build(self, workspace: Workspace) -> Path:
        """
        指定されたワークスペースから成果物をビルドし、そのパスを返します。

        Args:
            workspace (Workspace): ビルド対象のデータを含むワークスペース。

        Returns:
            Path: 生成された成果物のパス。
        """
        ...


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
        ...

    @classmethod
    def get_provider_name(cls) -> str:
        """プロバイダの名前を返すクラスメソッド。"""
        ...


@runtime_checkable
class IWorkProvider(IProvider, Protocol):
    """単一の作品を取得するためのインターフェース"""

    def get_work(self, work_id: Any) -> Workspace | None:
        """単一の作品を取得し、Workspaceを生成して返します。更新がない場合はNoneを返します。"""
        ...


@runtime_checkable
class IMultiWorkProvider(IProvider, Protocol):
    """作品群（シリーズ）を取得するためのインターフェース"""

    def get_multiple_works(self, collection_id: Any) -> List[Workspace]:
        """コレクション（シリーズなど）に含まれるすべての作品を取得し、Workspaceのリストを返します。"""
        ...


@runtime_checkable
class ICreatorProvider(IProvider, Protocol):
    """クリエイターの全作品を取得するためのインターフェース"""

    def get_creator_works(self, creator_id: Any) -> List[Workspace]:
        """特定のクリエイターが投稿したすべての作品を取得し、Workspaceのリストを返します。"""
        ...
