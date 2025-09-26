# src/pixiv2epub/models/workspace.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class Workspace:
    """自己完結したビルド可能なソースデータ単位を表す。"""

    id: str
    root_path: Path

    @property
    def source_path(self) -> Path:
        """小説のメタデータや本文ファイルが格納されるパス。"""
        return self.root_path / "source"

    @property
    def assets_path(self) -> Path:
        """画像やCSSなどの補助リソースが格納されるパス。"""
        return self.root_path / "assets"

    @property
    def manifest_path(self) -> Path:
        """ワークスペース自体のメタデータを記述したファイルのパス。"""
        return self.root_path / "manifest.json"


@dataclass(frozen=True)
class WorkspaceManifest:
    """ワークスペース自体のメタデータ。"""

    provider_name: str
    created_at_utc: str
    source_metadata: Dict[str, Any]
    workspace_schema_version: str = "1.0"
