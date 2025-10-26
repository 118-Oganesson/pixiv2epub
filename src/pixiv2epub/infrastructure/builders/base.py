# FILE: src/pixiv2epub/infrastructure/builders/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from ...models.domain import UnifiedContentManifest
from ...models.workspace import Workspace
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
    ) -> UnifiedContentManifest:
        """ビルド対象のメタデータを読み込みます。"""
        if custom_metadata:
            logger.debug("カスタムメタデータを使用してビルダーを初期化します。")
            return UnifiedContentManifest.model_validate(custom_metadata)

        try:
            return workspace.load_metadata()
        except FileNotFoundError as e:
            raise BuildError(f"ビルドに必要なメタデータが見つかりません: {e}") from e
        except Exception as e:
            raise BuildError(
                f"メタデータの読み込み中にエラーが発生しました: {e}"
            ) from e

    @classmethod
    @abstractmethod
    def get_builder_name(cls) -> str:
        """このビルダーの一意な名前を返します。"""
        raise NotImplementedError

    @abstractmethod
    def build(self, workspace: Workspace) -> Path:
        """ビルド処理を実行し、生成されたファイルのパスを返します。"""
        raise NotImplementedError
