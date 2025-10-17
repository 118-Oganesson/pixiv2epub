# FILE: src/pixiv2epub/infrastructure/builders/base.py
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from ...models.local import NovelMetadata
from ...models.workspace import Workspace

from ...shared.constants import DETAIL_FILE_NAME
from ...shared.exceptions import BuildError
from ...shared.settings import Settings


class BaseBuilder(ABC):
    """Builderの抽象基底クラス。"""

    def __init__(
        self,
        settings: Settings,
    ):
        """
        Args:
            settings (Settings): アプリケーション設定。
        """
        self.settings = settings

    def _load_metadata(
        self, workspace: Workspace, custom_metadata: Dict[str, Any] | None = None
    ) -> NovelMetadata:
        """ビルド対象のメタデータを読み込みます。"""
        if custom_metadata:
            metadata_dict = custom_metadata
            logger.debug("カスタムメタデータを使用してビルダーを初期化します。")
        else:
            detail_json_path = workspace.source_path / DETAIL_FILE_NAME
            if not detail_json_path.is_file():
                raise BuildError(
                    f"ビルドに必要な '{DETAIL_FILE_NAME}' が見つかりません: {detail_json_path}"
                )
            with open(detail_json_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)

        return NovelMetadata.model_validate(metadata_dict)

    @classmethod
    @abstractmethod
    def get_builder_name(cls) -> str:
        """このビルダーの一意な名前を返します。"""
        raise NotImplementedError

    @abstractmethod
    def build(self, workspace: Workspace) -> Path:
        """ビルド処理を実行し、生成されたファイルのパスを返します。"""
        raise NotImplementedError
