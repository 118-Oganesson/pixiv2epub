# src/pixiv2epub/app.py

import logging
from pathlib import Path
from typing import Any, List

from .core.coordinator import Coordinator
from .core.settings import Settings
from .utils.logging import setup_logging


class Pixiv2Epub:
    """
    設定とコアロジックをカプセル化し、アプリケーションの
    主要な機能を提供する中心的なクラス。
    """

    def __init__(self, settings: Settings):
        """
        Pixiv2Epubのインスタンスを初期化します。

        Args:
            settings (Settings): アプリケーション全体の設定オブジェクト。
        """
        self.settings = settings
        setup_logging(self.settings.log_level)
        self.coordinator = Coordinator(self.settings)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Pixiv2Epub application initialized.")

    def run_novel(self, novel_id: Any) -> Path:
        """単一の小説をダウンロードし、ビルドします。"""
        return self.coordinator.download_and_build_novel(
            provider_name="pixiv",
            builder_name="epub",
            novel_id=novel_id,
        )

    def run_series(self, series_id: Any) -> List[Path]:
        """シリーズをダウンロードし、ビルドします。"""
        return self.coordinator.download_and_build_series(
            provider_name="pixiv",
            builder_name="epub",
            series_id=series_id,
        )

    def run_user_novels(self, user_id: Any) -> List[Path]:
        """ユーザーの全作品をダウンロードし、ビルドします。"""
        return self.coordinator.download_and_build_user_novels(
            provider_name="pixiv", builder_name="epub", user_id=user_id
        )

    def download_novel(self, novel_id: Any) -> Path:
        """単一の小説をダウンロードのみ行います。"""
        provider = self.coordinator._get_provider("pixiv")
        return provider.get_novel(novel_id)

    def download_series(self, series_id: Any) -> List[Path]:
        """シリーズ作品をダウンロードのみ行います。"""
        provider = self.coordinator._get_provider("pixiv")
        return provider.get_series(series_id)

    def download_user_novels(self, user_id: Any) -> List[Path]:
        """ユーザーの全作品をダウンロードのみ行います。"""
        provider = self.coordinator._get_provider("pixiv")
        return provider.get_user_novels(user_id)

    def build_from_directory(self, novel_dir: Path) -> Path:
        """ローカルディレクトリからビルドのみ行います。"""
        builder = self.coordinator._get_builder("epub", novel_dir)
        return builder.build()
