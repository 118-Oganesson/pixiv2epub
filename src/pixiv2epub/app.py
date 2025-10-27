# FILE: src/pixiv2epub/app.py
from pathlib import Path

from loguru import logger

from .domain.interfaces import IBuilder
from .models.workspace import Workspace
from .shared.exceptions import AssetMissingError
from .shared.settings import Settings


class Application:
    """設定をカプセル化し、アプリケーションのドメイン横断的な機能を提供するクラス。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        logger.debug('Pixiv2Epubアプリケーションが初期化されました。')

    def build_from_workspace(
        self,
        workspace_path: Path,
        builder: IBuilder,
    ) -> Path:
        """ローカルのワークスペースからEPUBを生成します。"""
        try:
            workspace = Workspace.from_path(workspace_path)
            return builder.build(workspace)
        except ValueError as e:
            raise AssetMissingError(
                f'指定されたパスは有効なワークスペースではありません: {workspace_path}'
            ) from e
