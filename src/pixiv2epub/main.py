# src/pixiv2epub/main.py

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .orchestration.coordinator import Coordinator
from .utils.config import load_config
from .utils.logging import setup_logging


class Pixiv2Epub:
    """
    設定とコアロジックをカプセル化し、アプリケーションの
    主要な機能を提供する中心的なクラス。
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
        log_level: str = "INFO",
    ):
        """
        Pixiv2Epubのインスタンスを初期化します。

        Args:
            config (Optional[Dict[str, Any]]): 事前に読み込まれた設定辞書。
            config_path (Optional[str]): 設定ファイルのパス。
            log_level (str): ログレベル。
        """
        setup_logging(log_level)
        self.config = config if config is not None else load_config(config_path)
        self.coordinator = Coordinator(self.config)
        self.logger = logging.getLogger(self.__class__.__name__)

    def run_novel(self, novel_id: Any, cleanup: Optional[bool] = None) -> Path:
        """単一の小説をダウンロードし、ビルドします。"""
        return self.coordinator.download_and_build_novel(
            provider_name="pixiv",
            builder_name="epub",
            novel_id=novel_id,
            cleanup=cleanup,
        )

    def run_series(self, series_id: Any, cleanup: Optional[bool] = None) -> List[Path]:
        """シリーズをダウンロードし、ビルドします。"""
        return self.coordinator.download_and_build_series(
            provider_name="pixiv",
            builder_name="epub",
            series_id=series_id,
            cleanup=cleanup,
        )

    def run_user_novels(
        self, user_id: Any, cleanup: Optional[bool] = None
    ) -> List[Path]:
        """ユーザーの全作品をダウンロードし、ビルドします。"""
        return self.coordinator.download_and_build_user_novels(
            provider_name="pixiv", builder_name="epub", user_id=user_id, cleanup=cleanup
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
