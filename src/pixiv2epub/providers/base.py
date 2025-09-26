# src/pixiv2epub/providers/base.py

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List

from ..core.settings import Settings


class BaseProvider(ABC):
    """データソースプロバイダの抽象基底クラス。"""

    def __init__(self, settings: Settings):
        """
        プロバイダの初期化。

        Args:
            settings (Settings): アプリケーション全体の設定情報。
        """
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__} を初期化しました。")

    @classmethod
    @abstractmethod
    def get_provider_name(cls) -> str:
        """プロバイダの名前を返すクラスメソッド。"""
        pass

    @abstractmethod
    def get_novel(self, novel_id: Any) -> Path:
        """単一の小説を取得し、ローカルに保存します。"""
        pass

    @abstractmethod
    def get_series(self, series_id: Any) -> List[Path]:
        """シリーズに含まれるすべての小説を取得し、ローカルに保存します。"""
        pass

    @abstractmethod
    def get_user_novels(self, user_id: Any) -> List[Path]:
        """特定のユーザーが投稿したすべての小説を取得し、ローカルに保存します。"""
        pass
