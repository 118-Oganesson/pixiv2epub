# FILE: src/pixiv2epub/domain/interfaces.py
from pathlib import Path
from typing import Protocol

from ..models.workspace import Workspace


class IBuilder(Protocol):
    """成果物をビルドするためのインターフェース。"""

    def build(self, workspace: Workspace) -> Path:
        """
        指定されたワークスペースから成果物をビルドし、そのパスを返します。

        Args:
            workspace (Workspace): ビルド対象のデータを含むワークスペース。

        Returns:
            Path: 生成された成果物のパス。
        """
        ...
