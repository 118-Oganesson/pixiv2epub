# FILE: src/pixiv2epub/infrastructure/builders/epub/builder.py
import os
import json
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from loguru import logger

from ....models.workspace import Workspace
from ....shared.exceptions import BuildError
from ....shared.settings import Settings
from ....utils.filesystem_sanitizer import generate_sanitized_path
from ..base import BaseBuilder
from .asset_manager import AssetManager
from .component_generator import EpubComponentGenerator
from .package_assembler import EpubPackageAssembler


class EpubBuilder(BaseBuilder):
    """EPUB生成プロセスを統括するクラス。"""

    def __init__(
        self,
        workspace: Workspace,
        settings: Settings,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(workspace, settings, custom_metadata)

        # manifestからプロバイダー名を取得
        provider_name = "default"  # フォールバック先
        try:
            with open(self.workspace.manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            provider_name = manifest.get("provider_name", "default")
            logger.debug(f"Provider '{provider_name}' のテーマを使用します。")
        except (IOError, json.JSONDecodeError):
            logger.warning(
                "manifest.jsonが読み取れないため、デフォルトテーマを使用します。"
            )

        # テンプレートディレクトリを動的に設定
        assets_root = Path(__file__).parent.parent.parent.parent / "assets"
        epub_assets_root = assets_root / "epub"

        provider_template_dir = epub_assets_root / provider_name
        default_template_dir = epub_assets_root / "default"

        # プロバイダー固有のテーマ -> デフォルトテーマの順で探すローダーを設定
        # 存在しないディレクトリを渡すとエラーになるため、存在チェックを行う
        loaders = []
        if provider_template_dir.is_dir() and provider_name != "default":
            loaders.append(FileSystemLoader(str(provider_template_dir)))

        if default_template_dir.is_dir():
            loaders.append(FileSystemLoader(str(default_template_dir)))
        else:
            raise BuildError(
                f"デフォルトのテンプレートディレクトリが見つかりません: {default_template_dir}"
            )

        loader = ChoiceLoader(loaders)

        # EpubComponentGeneratorに渡すEnvironmentを差し替える
        template_env = Environment(loader=loader, autoescape=True)

        self.asset_manager = AssetManager(
            self.workspace,
            self.metadata,
        )
        # generatorの初期化を修正
        self.generator = EpubComponentGenerator(
            self.metadata, self.workspace, template_env
        )
        self.archiver = EpubPackageAssembler(self.settings)

    @classmethod
    def get_builder_name(cls) -> str:
        return "epub"

    def build(self) -> Path:
        """EPUBファイルを生成するメインの実行メソッド。"""
        output_path = self._determine_output_path()
        logger.info(f"EPUB作成処理を開始します (Workspace: {self.workspace.id})")
        if output_path.exists():
            logger.warning(
                f"出力ファイル {output_path} は既に存在するため、上書きします。"
            )

        try:
            final_images, raw_pages_info, cover_asset = (
                self.asset_manager.gather_assets()
            )
            components = self.generator.generate_components(
                final_images,
                raw_pages_info,
                cover_asset,
            )
            self.archiver.archive(components, output_path)
            logger.info(f"EPUBファイルの作成に成功しました: {output_path}")
            return output_path
        except Exception as e:
            logger.exception("EPUBファイルの作成中に致命的なエラーが発生しました。")
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
            "id": self.metadata.identifier.get("novel_id")
            or self.metadata.identifier.get("post_id", "0"),
            "author_name": self.metadata.authors.name or "unknown_author",
            "author_id": str(self.metadata.authors.id or "0"),
            "series_title": self.metadata.series.title if self.metadata.series else "",
            "series_id": str(self.metadata.series.id if self.metadata.series else "0"),
        }

        safe_relative_path = generate_sanitized_path(
            template,
            template_vars,
            max_length=self.settings.builder.max_filename_length,
        )

        output_dir_base = self.settings.builder.output_directory
        final_path = output_dir_base.resolve() / safe_relative_path
        final_path.parent.mkdir(parents=True, exist_ok=True)
        return final_path

    def _cleanup_failed_build(self, path: Path):
        """ビルド失敗時に、不完全な出力ファイルを削除します。"""
        try:
            if path.exists():
                os.remove(path)
                logger.info(f"不完全な出力ファイルを削除しました: {path}")
        except OSError as e:
            logger.error(f"出力ファイルの削除に失敗しました: {path}, {e}")
