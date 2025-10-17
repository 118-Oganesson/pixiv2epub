# FILE: src/pixiv2epub/models/workspace.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..shared.constants import MANIFEST_FILE_NAME


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
        return self.root_path / MANIFEST_FILE_NAME

    @classmethod
    def from_path(cls, path: Path) -> "Workspace":
        """
        指定されたパスからWorkspaceインスタンスを生成します。
        パスに 'manifest.json' が存在しない場合はValueErrorを送出します。
        """
        manifest_path = path / MANIFEST_FILE_NAME
        if not manifest_path.is_file():
            raise ValueError(
                f"指定されたパスにマニフェストファイルが見つかりません: {path}"
            )
        return cls(id=path.name, root_path=path.resolve())


@dataclass(frozen=True)
class WorkspaceManifest:
    """ワークスペース自体のメタデータ。"""

    provider_name: str
    created_at_utc: str
    source_metadata: Dict[str, Any]
    content_hash: Optional[str] = None
    workspace_schema_version: str = "1.0"
