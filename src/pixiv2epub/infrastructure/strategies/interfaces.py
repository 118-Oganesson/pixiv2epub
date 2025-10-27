# FILE: src/pixiv2epub/infrastructure/providers/strategies/interfaces.py
from abc import ABC, abstractmethod
from pathlib import Path

from ...models.domain import UnifiedContentManifest
from ...models.workspace import Workspace


class IContentParser(ABC):
    """
    APIレスポンスから取得した本文データをHTMLに変換する戦略インターフェース。
    """

    @abstractmethod
    def parse(self, raw_content: object, image_paths: dict[str, Path]) -> str:
        """APIレスポンスの本文をパースし、単一のHTML文字列を返す。"""
        raise NotImplementedError


class IMetadataMapper(ABC):
    """
    APIレスポンスをアプリケーション内部のメタデータモデルに変換する戦略インターフェース。
    """

    @abstractmethod
    def map_to_metadata(
        self,
        workspace: Workspace,
        cover_path: Path | None,
        **kwargs: object,
    ) -> UnifiedContentManifest:
        """APIレスポンスを UnifiedContentManifest に変換する。"""
        raise NotImplementedError
