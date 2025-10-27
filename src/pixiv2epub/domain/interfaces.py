# FILE: src/pixiv2epub/domain/interfaces.py

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..models.domain import UnifiedContentManifest
from ..models.fanbox import Post
from ..models.pixiv import NovelApiResponse
from ..models.workspace import Workspace, WorkspaceManifest
from ..shared.enums import ContentType
from ..shared.enums import Provider as ProviderEnum
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
class IPixivImageDownloader(Protocol):
    """Pixivの画像ダウンロード処理の振る舞いを定義するプロトコル。"""

    def download_cover(
        self, novel_detail: dict[str, Any], image_dir: Path
    ) -> Path | None:
        """小説の表紙画像をダウンロードします。"""
        ...

    def download_embedded_images(
        self, novel_data: NovelApiResponse, image_dir: Path
    ) -> dict[str, Path]:
        """本文中のすべての画像をダウンロードし、IDとパスのマッピングを返します。"""
        ...


@runtime_checkable
class IFanboxImageDownloader(Protocol):
    """Fanboxの画像ダウンロード処理の振る舞いを定義するプロトコル。"""

    def download_cover(self, post_data: Post, image_dir: Path) -> Path | None:
        """投稿のカバー画像をダウンロードします。"""
        ...

    def download_embedded_images(
        self, post_data: Post, image_dir: Path
    ) -> dict[str, Path]:
        """本文中のすべての画像をダウンロードし、IDとパスのマッピングを返します。"""
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


@runtime_checkable
class IProviderFactory(Protocol):
    """Providerインスタンスを生成するためのファクトリのインターフェース。"""

    def create(self, provider_type: ProviderEnum) -> IProvider:
        """指定された種類のProviderインスタンスを生成し、依存関係を注入して返します。"""
        ...
