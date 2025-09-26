# src/pixiv2epub/builders/epub/builder.py

import os
from pathlib import Path
from typing import Any, Dict, Optional

from ...core.exceptions import BuildError
from ...core.settings import Settings
from ...utils.path_manager import generate_sanitized_path
from ..base import BaseBuilder
from .archiver import Archiver
from .asset_manager import AssetManager
from .generator import EpubGenerator


class EpubBuilder(BaseBuilder):
    """EPUB生成プロセスを統括するクラス。"""

    def __init__(
        self,
        novel_dir: Path,
        settings: Settings,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(novel_dir, settings, custom_metadata)
        css_rel_path = self.settings.builder.css_file
        self.css_abs_path: Optional[Path] = None
        if css_rel_path:
            if (self.novel_dir / css_rel_path).is_file():
                self.css_abs_path = self.novel_dir / css_rel_path
            elif Path(css_rel_path).is_file():
                self.css_abs_path = Path(css_rel_path).resolve()
            else:
                self.logger.warning(
                    f"指定されたCSSファイルが見つかりません: {css_rel_path}"
                )

        # assetsディレクトリのパスを解決
        asset_dir = Path(__file__).parent.parent.parent / "assets"

        self.asset_manager = AssetManager(self.paths, self.metadata, self.css_abs_path)
        self.generator = EpubGenerator(self.metadata, self.paths, asset_dir)
        self.archiver = Archiver(self.settings)

    @classmethod
    def get_builder_name(cls) -> str:
        return "epub"

    def build(self) -> Path:
        """EPUBファイルを生成するメインの実行メソッド。"""
        output_path = self._determine_output_path()
        self.logger.info(f"EPUB作成処理を開始します: {self.novel_dir.name}")
        if output_path.exists():
            self.logger.warning(
                f"出力ファイル {output_path} は既に存在するため、上書きします。"
            )

        try:
            final_images, raw_pages_info, cover_asset = (
                self.asset_manager.gather_assets()
            )
            components = self.generator.generate_components(
                final_images, raw_pages_info, cover_asset, self.css_abs_path
            )
            self.archiver.archive(components, output_path)
            self.logger.info(f"EPUBファイルの作成に成功しました: {output_path}")
            return output_path
        except Exception as e:
            self.logger.exception(
                "EPUBファイルの作成中に致命的なエラーが発生しました。"
            )
            self._cleanup_failed_build(output_path)
            raise BuildError(f"EPUBのビルドに失敗しました: {e}") from e

    def _determine_output_path(self) -> Path:
        """メタデータと設定に基づき、最終的な出力ファイルパスを決定します。"""
        if self.metadata.series and self.settings.builder.series_filename_template:
            template = self.settings.builder.series_filename_template
        else:
            template = self.settings.builder.filename_template

        template_vars = {
            "title": self.metadata.title or "untitled",
            "id": self.metadata.identifier.get("novel_id", "0"),
            "author_name": self.metadata.authors.name or "unknown_author",
            "author_id": str(self.metadata.authors.id or "0"),
            "series_title": self.metadata.series.title if self.metadata.series else "",
            "series_id": str(self.metadata.series.id if self.metadata.series else "0"),
        }

        safe_relative_path = generate_sanitized_path(template, template_vars)
        output_dir_base = self.settings.builder.output_directory
        final_path = output_dir_base.resolve() / safe_relative_path
        final_path.parent.mkdir(parents=True, exist_ok=True)
        return final_path

    def _cleanup_failed_build(self, path: Path):
        """ビルド失敗時に、不完全な出力ファイルを削除します。"""
        try:
            if path.exists():
                os.remove(path)
                self.logger.info(f"不完全な出力ファイルを削除しました: {path}")
        except OSError as e:
            self.logger.error(f"出力ファイルの削除に失敗しました: {path}, {e}")
