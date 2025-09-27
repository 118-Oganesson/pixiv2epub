# src/pixiv2epub/app.py

import logging
from pathlib import Path
from typing import Any, List

from .core.coordinator import Coordinator
from .core.settings import Settings
from .models.workspace import Workspace
from .utils.logging import setup_logging


class Application:
    """
    設定とコアロジックをカプセル化し、アプリケーションの
    主要な機能を提供する中心的なクラス。
    """

    def __init__(self, settings: Settings):
        """
        Applicationのインスタンスを初期化します。
        このインスタンスはアプリケーション実行中、一貫して使用されます。

        Args:
            settings (Settings): アプリケーション全体の設定オブジェクト。
        """
        self.settings = settings
        setup_logging(self.settings.log_level)
        self.coordinator = Coordinator(self.settings)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Pixiv2Epubアプリケーションが初期化されました。")

    # --- 通常実行 (Download & Build) ---

    def run_novel(self, novel_id: Any) -> Path:
        """単一のPixiv小説をダウンロードし、EPUBを生成します。"""
        return self.coordinator.download_and_build_novel(
            provider_name="pixiv",
            builder_name="epub",
            novel_id=novel_id,
        )

    def run_series(self, series_id: Any) -> List[Path]:
        """Pixivのシリーズをダウンロードし、EPUBを生成します。"""
        return self.coordinator.download_and_build_series(
            provider_name="pixiv",
            builder_name="epub",
            series_id=series_id,
        )

    def run_user_novels(self, user_id: Any) -> List[Path]:
        """Pixivユーザーの全作品をダウンロードし、EPUBを生成します。"""
        return self.coordinator.download_and_build_user_novels(
            provider_name="pixiv", builder_name="epub", user_id=user_id
        )

    # --- 分割実行 ---

    def download_novel(self, novel_id: Any) -> Workspace:
        """単一の小説をダウンロードのみ行い、ワークスペースを返します。"""
        provider = self.coordinator._get_provider("pixiv")
        return provider.get_novel(novel_id)

    def download_series(self, series_id: Any) -> List[Workspace]:
        """シリーズ作品をダウンロードのみ行い、ワークスペースのリストを返します。"""
        provider = self.coordinator._get_provider("pixiv")
        return provider.get_series(series_id)

    def download_user_novels(self, user_id: Any) -> List[Workspace]:
        """ユーザーの全作品をダウンロードのみ行い、ワークスペースのリストを返します。"""
        provider = self.coordinator._get_provider("pixiv")
        return provider.get_user_novels(user_id)

    def build_from_workspace(self, workspace_path: Path) -> Path:
        """ローカルのワークスペースからEPUBを生成します。"""
        if not (workspace_path / "manifest.json").is_file():
            raise FileNotFoundError(
                f"指定されたパスに manifest.json が見つかりません: {workspace_path}"
            )

        # パスからWorkspaceオブジェクトを復元
        workspace = Workspace(
            id=workspace_path.name, root_path=workspace_path.resolve()
        )

        builder = self.coordinator._get_builder("epub", workspace)
        return builder.build()
