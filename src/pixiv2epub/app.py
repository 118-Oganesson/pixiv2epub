# FILE: src/pixiv2epub/app.py
from pathlib import Path
from typing import Any, List

from loguru import logger

from .domain.interfaces import IBuilder
from .domain.orchestrator import DownloadBuildOrchestrator
from .infrastructure.providers.base import (
    ICreatorProvider,
    IMultiWorkProvider,
    IProvider,
    IWorkProvider,
)
from .models.workspace import Workspace
from .shared.constants import MANIFEST_FILE_NAME
from .shared.enums import ContentType
from .shared.exceptions import AssetMissingError
from .shared.settings import Settings


class Application:
    """
    設定とドメインロジックをカプセル化し、アプリケーションの
    主要な機能を提供する中心的なクラス。
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        logger.debug("Pixiv2Epubアプリケーションが初期化されました。")

    def run_download_and_build(
        self,
        provider: IProvider,
        content_type: ContentType,
        target_id: Any,
        builder: IBuilder,
    ) -> List[Path]:
        """
        指定されたターゲットをダウンロードし、EPUBをビルドする一連の処理を実行します。
        """
        orchestrator = DownloadBuildOrchestrator(provider, builder, self.settings)

        if content_type == ContentType.WORK:
            result = orchestrator.process_work(target_id)
            return [result] if result else []
        elif content_type == ContentType.SERIES:
            return orchestrator.process_collection(target_id, is_series=True)
        elif content_type == ContentType.CREATOR:
            return orchestrator.process_collection(target_id, is_series=False)
        else:
            raise ValueError(
                f"サポートされていないコンテンツタイプです: {content_type}"
            )

    def run_download_only(
        self,
        provider: IProvider,
        content_type: ContentType,
        target_id: Any,
    ) -> List[Workspace]:
        """
        指定されたターゲットのダウンロードのみを実行し、ワークスペースを返します。
        """
        if content_type == ContentType.WORK and isinstance(provider, IWorkProvider):
            ws = provider.get_work(target_id)
            return [ws] if ws else []
        elif content_type == ContentType.SERIES and isinstance(
            provider, IMultiWorkProvider
        ):
            return provider.get_multiple_works(target_id)
        elif content_type == ContentType.CREATOR and isinstance(
            provider, ICreatorProvider
        ):
            return provider.get_creator_works(target_id)
        else:
            raise TypeError(
                f"現在のProviderは {content_type.name} のダウンロードをサポートしていません。"
            )

    def build_from_workspace(
        self,
        workspace_path: Path,
        builder: IBuilder,
    ) -> Path:
        """ローカルのワークスペースからEPUBを生成します。"""
        if not (workspace_path / MANIFEST_FILE_NAME).is_file():
            raise AssetMissingError(
                f"指定されたパスに {MANIFEST_FILE_NAME} が見つかりません: {workspace_path}"
            )

        workspace = Workspace(
            id=workspace_path.name, root_path=workspace_path.resolve()
        )

        return builder.build(workspace)
