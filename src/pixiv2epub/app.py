# FILE: src/pixiv2epub/app.py
from pathlib import Path
from typing import Any, List

from loguru import logger

from .domain.orchestrator import DownloadBuildOrchestrator
from .infrastructure.builders.epub.builder import EpubBuilder
from .infrastructure.providers.fanbox.provider import FanboxProvider
from .infrastructure.providers.pixiv.provider import PixivProvider
from .models.workspace import Workspace
from .shared.settings import Settings
from .utils.logging import setup_logging


class Application:
    """
    設定とドメインロジックをカプセル化し、アプリケーションの
    主要な機能を提供する中心的なクラス。
    依存性の注入(DI)の管理も担当する。
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        setup_logging(self.settings.log_level)
        logger.debug("Pixiv2Epubアプリケーションが初期化されました。")

    def _create_orchestrator(self, provider_name: str) -> DownloadBuildOrchestrator:
        """
        具体的なProviderとBuilderをインスタンス化し、Orchestratorを生成する。
        """
        if provider_name == "pixiv":
            provider = PixivProvider(self.settings)
        elif provider_name == "fanbox":
            provider = FanboxProvider(self.settings)
        else:
            raise ValueError(f"サポートされていないプロバイダーです: {provider_name}")

        builder_class = EpubBuilder
        return DownloadBuildOrchestrator(provider, builder_class, self.settings)

    # --- 汎用実行メソッド ---

    def process_pixiv_work_to_epub(self, work_id: Any) -> Path:
        """単一のPixiv作品をダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("pixiv")
        return orchestrator.process_work(work_id)

    def process_pixiv_series_to_epub(self, series_id: Any) -> List[Path]:
        """Pixivのシリーズをダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("pixiv")
        return orchestrator.process_multiple_works(series_id)

    def process_pixiv_user_works_to_epub(self, user_id: Any) -> List[Path]:
        """Pixivユーザーの全作品をダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("pixiv")
        return orchestrator.process_creator_works(user_id)

    def process_fanbox_work_to_epub(self, work_id: Any) -> Path:
        """単一のFanbox投稿をダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("fanbox")
        return orchestrator.process_work(work_id)

    def process_fanbox_creator_to_epub(self, creator_id: Any) -> List[Path]:
        """Fanboxクリエイターの全投稿をダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("fanbox")
        return orchestrator.process_creator_works(creator_id)

    # --- 分割実行 ---

    def download_pixiv_work(self, work_id: Any) -> Workspace:
        """単一のPixiv作品をダウンロードのみ行い、ワークスペースを返します。"""
        provider = PixivProvider(self.settings)
        return provider.get_work(work_id)

    def download_pixiv_series(self, series_id: Any) -> List[Workspace]:
        """Pixivシリーズ作品をダウンロードのみ行い、ワークスペースのリストを返します。"""
        provider = PixivProvider(self.settings)
        return provider.get_multiple_works(series_id)

    def download_pixiv_user_works(self, user_id: Any) -> List[Workspace]:
        """Pixivユーザーの全作品をダウンロードのみ行い、ワークスペースのリストを返します。"""
        provider = PixivProvider(self.settings)
        return provider.get_creator_works(user_id)

    def download_fanbox_work(self, work_id: Any) -> Workspace:
        """単一のFanbox投稿をダウンロードのみ行い、ワークスペースを返します。"""
        provider = FanboxProvider(self.settings)
        return provider.get_work(work_id)

    def build_from_workspace(self, workspace_path: Path) -> Path:
        """ローカルのワークスペースからEPUBを生成します。"""
        if not (workspace_path / "manifest.json").is_file():
            raise FileNotFoundError(
                f"指定されたパスに manifest.json が見つかりません: {workspace_path}"
            )

        workspace = Workspace(
            id=workspace_path.name, root_path=workspace_path.resolve()
        )

        builder = EpubBuilder(workspace=workspace, settings=self.settings)
        return builder.build()
