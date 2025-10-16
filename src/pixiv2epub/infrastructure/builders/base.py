# FILE: src/pixiv2epub/infrastructure/builders/base.py
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from ...models.local import NovelMetadata
from ...models.workspace import Workspace
from ...shared.exceptions import BuildError
from ...shared.settings import Settings


class BaseBuilder(ABC):
    """Builderの抽象基底クラス。"""

    def __init__(
        self,
        workspace: Workspace,
        settings: Settings,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            workspace (Workspace): ビルド対象のデータを含むワークスペース。
            settings (Settings): アプリケーション設定。
            custom_metadata (Optional[Dict[str, Any]]): detail.jsonの代わりのメタデータ。
        """
        self.workspace = workspace
        self.settings = settings

        if custom_metadata:
            metadata_dict = custom_metadata
            logger.debug("カスタムメタデータを使用してビルダーを初期化します。")
        else:
            detail_json_path = self.workspace.source_path / "detail.json"
            if not detail_json_path.is_file():
                raise BuildError(
                    f"ビルドに必要な 'detail.json' が見つかりません: {detail_json_path}"
                )
            with open(detail_json_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)

        self.metadata = NovelMetadata.model_validate(metadata_dict)

    @classmethod
    @abstractmethod
    def get_builder_name(cls) -> str:
        """このビルダーの一意な名前を返します。"""
        raise NotImplementedError

    @abstractmethod
    def build(self) -> Path:
        """ビルド処理を実行し、生成されたファイルのパスを返します。"""
        raise NotImplementedError
