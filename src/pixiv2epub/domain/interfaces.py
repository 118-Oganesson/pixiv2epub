# FILE: src/pixiv2epub/domain/interfaces.py

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..models.domain import UnifiedContentManifest
from ..models.workspace import Workspace, WorkspaceManifest
from ..shared.enums import ContentType
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

    def __init__(self, settings: Settings): ...

    @classmethod
    def get_provider_name(cls) -> str:
        """プロバイダの名前を返すクラスメソッド。"""
        ...

    def get_works(
        self, identifier: int | str, content_type: ContentType
    ) -> list[Workspace]:
        """
        指定された識別子とコンテンツ種別に基づいて作品を取得し、
        処理済みのWorkspaceのリストを返します。
        更新がない、または処理対象が存在しない場合は空のリストを返します。
        """
        ...


@runtime_checkable
class IWorkspaceRepository(Protocol):
    """ワークスペースのファイルシステム操作を抽象化するインターフェース。"""

    def setup_workspace(self, content_id: int | str, provider_name: str) -> Workspace:
        """content_idに基づいた永続的なワークスペースを準備します。"""
        ...

    def get_workspace_path(self, content_id: int | str, provider_name: str) -> Path:
        """
        content_idに基づいて永続的なワークスペースのルートパスを計算して返します。
        このメソッドはファイルシステムへの書き込みを行いません。
        """
        ...

    def persist_metadata(
        self,
        workspace: Workspace,
        metadata: UnifiedContentManifest,
        manifest: WorkspaceManifest,
    ) -> None:
        """メタデータとマニフェストをワークスペースに永続化します。"""
        ...
