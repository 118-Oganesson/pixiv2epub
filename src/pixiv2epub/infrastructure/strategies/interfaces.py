# FILE: src/pixiv2epub/infrastructure/providers/strategies/interfaces.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ...models.local import NovelMetadata
from ...models.workspace import Workspace


class IUpdateCheckStrategy(ABC):
    """
    コンテンツの更新が必要かどうかを判断するための戦略インターフェース。
    """

    @abstractmethod
    def is_update_required(
        self, workspace: Workspace, api_response: Dict
    ) -> Tuple[bool, str]:
        """更新が必要か判断し、(更新フラグ, 新コンテンツ識別子) を返す。"""
        raise NotImplementedError


class IContentParser(ABC):
    """
    APIレスポンスから取得した本文データをHTMLに変換する戦略インターフェース。
    """

    @abstractmethod
    def parse(self, raw_content: Any, image_paths: Dict[str, Path]) -> str:
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
        cover_path: Optional[Path],
        **kwargs: Any,
    ) -> NovelMetadata:
        """APIレスポンスを NovelMetadata に変換する。"""
        raise NotImplementedError
