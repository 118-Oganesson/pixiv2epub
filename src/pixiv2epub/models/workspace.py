# FILE: src/pixiv2epub/models/workspace.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models.domain import UnifiedContentManifest
from ..shared.constants import DETAIL_FILE_NAME, MANIFEST_FILE_NAME


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

    def load_metadata(self) -> UnifiedContentManifest:
        """
        ワークスペースからdetail.jsonを読み込み、UnifiedContentManifestを返します。

        Raises:
            FileNotFoundError: メタデータファイルが見つからない場合。
        """
        detail_path = self.source_path / DETAIL_FILE_NAME
        return UnifiedContentManifest.load(detail_path)

    def get_page_content(self, page_body_path: str) -> str:
        """
        ページ情報から本文コンテンツの文字列を返します。

        Args:
            page_body_path (str): "./page-1.xhtml" のような相対パス。

        Raises:
            FileNotFoundError: ページファイルが見つからない場合。

        Returns:
             str: ページのHTMLコンテンツ。
        """
        page_file = self.source_path / page_body_path.lstrip("./")
        if not page_file.is_file():
            raise FileNotFoundError(f"ページファイルが見つかりません: {page_file}")
        return page_file.read_text(encoding="utf-8")


@dataclass(frozen=True)
class WorkspaceManifest:
    """ワークスペース自体のメタデータ。"""

    provider_name: str
    created_at_utc: str
    source_identifier: str
    content_etag: str | None = None
    workspace_schema_version: str = "1.0"
    provider_specific_data: dict[str, Any] | None = None
