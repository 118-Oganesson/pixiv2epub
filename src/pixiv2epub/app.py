# FILE: src/pixiv2epub/app.py
from pathlib import Path
from typing import Any, List

from loguru import logger

from .domain.orchestrator import DownloadBuildOrchestrator
from .infrastructure.builders.epub.builder import EpubBuilder
from .infrastructure.providers.pixiv.provider import PixivProvider
from .infrastructure.providers.fanbox.provider import FanboxProvider
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

    # --- Pixiv用実行メソッド ---

    def process_novel_to_epub(self, novel_id: Any) -> Path:
        """単一のPixiv小説をダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("pixiv")
        return orchestrator.process_novel(novel_id)

    def process_series_to_epub(self, series_id: Any) -> List[Path]:
        """Pixivのシリーズをダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("pixiv")
        return orchestrator.process_series(series_id)

    def process_user_novels_to_epub(self, user_id: Any) -> List[Path]:
        """Pixivユーザーの全作品をダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("pixiv")
        return orchestrator.process_user_novels(user_id)

    # --- Fanbox用実行メソッド (参考) ---
    def process_fanbox_post_to_epub(self, post_id: Any) -> Path:
        """単一のFanbox投稿をダウンロードし、EPUBを生成します。"""
        orchestrator = self._create_orchestrator("fanbox")
        # Orchestratorは汎用的なので、FanboxProviderが返すWorkspaceを処理できる
        # FanboxProviderに `get_novel` という名前のメソッドがあればそのまま使える
        # ここでは `get_post` を呼び出すようにOrchestratorを拡張するか、Providerのメソッド名を合わせる想定
        return orchestrator.process_novel(
            post_id
        )  # process_novelが内部でprovider.get_novelを呼ぶ

    # --- 分割実行 ---

    def download_novel(self, novel_id: Any) -> Workspace:
        """単一のPixiv小説をダウンロードのみ行い、ワークスペースを返します。"""
        provider = PixivProvider(self.settings)
        return provider.get_novel(novel_id)

    def download_series(self, series_id: Any) -> List[Workspace]:
        """Pixivシリーズ作品をダウンロードのみ行い、ワークスペースのリストを返します。"""
        provider = PixivProvider(self.settings)
        return provider.get_series(series_id)

    def download_user_novels(self, user_id: Any) -> List[Workspace]:
        """Pixivユーザーの全作品をダウンロードのみ行い、ワークスペースのリストを返します。"""
        provider = PixivProvider(self.settings)
        return provider.get_user_novels(user_id)

    def download_fanbox_post(self, post_id: Any) -> Workspace:
        """単一のFanbox投稿をダウンロードのみ行い、ワークスペースを返します。"""
        provider = FanboxProvider(self.settings)
        return provider.get_post(post_id)

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
