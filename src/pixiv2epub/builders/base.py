# src/pixiv2epub/builders/base.py

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.exceptions import BuildError
from ..core.settings import Settings
from ..models.local import NovelMetadata
from ..utils.path_manager import PathManager


class BaseBuilder(ABC):
    """Builderの抽象基底クラス。"""

    def __init__(
        self,
        novel_dir: Path,
        settings: Settings,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            novel_dir (Path): 小説データが格納されているディレクトリ。
            settings (Settings): アプリケーション設定。
            custom_metadata (Optional[Dict[str, Any]]): detail.jsonの代わりのメタデータ。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.novel_dir = novel_dir.resolve()
        self.settings = settings

        if custom_metadata:
            metadata_dict = custom_metadata
            self.logger.debug("カスタムメタデータを使用してビルダーを初期化します。")
        else:
            detail_json_path = self.novel_dir / "detail.json"
            if not detail_json_path.is_file():
                raise BuildError(
                    f"ビルドに必要な 'detail.json' が見つかりません: {detail_json_path}"
                )
            with open(detail_json_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)

        self.metadata = NovelMetadata.from_dict(metadata_dict)
        self.paths = PathManager(
            base_dir=self.novel_dir.parent, novel_dir_name=self.novel_dir.name
        )

    @classmethod
    @abstractmethod
    def get_builder_name(cls) -> str:
        """このビルダーの一意な名前を返します。"""
        raise NotImplementedError

    @abstractmethod
    def build(self) -> Path:
        """ビルド処理を実行し、生成されたファイルのパスを返します。"""
        raise NotImplementedError
