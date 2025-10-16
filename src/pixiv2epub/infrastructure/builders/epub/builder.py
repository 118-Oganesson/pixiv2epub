# FILE: src/pixiv2epub/infrastructure/builders/epub/builder.py
import os
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from loguru import logger

from ....models.local import NovelMetadata
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
        settings: Settings,
    ):
        super().__init__(settings)
        self.archiver = EpubPackageAssembler(self.settings)

    @classmethod
    def get_builder_name(cls) -> str:
        return "epub"

    def build(self, workspace: Workspace) -> Path:
        """EPUBファイルを生成するメインの実行メソッド。"""
        metadata = self._load_metadata(workspace)
        output_path = self._determine_output_path(metadata)
        logger.info("EPUB作成処理を開始します (Workspace: {})", workspace.id)
        if output_path.exists():
            logger.warning(
                "出力ファイル {} は既に存在するため、上書きします。", output_path
            )

        try:
            # テンプレートエンジンとジェネレータを動的に初期化
            template_env = self._create_template_env(workspace)
            asset_manager = AssetManager(workspace, metadata)
            generator = EpubComponentGenerator(metadata, workspace, template_env)

            final_images, raw_pages_info, cover_asset = asset_manager.gather_assets()
            components = generator.generate_components(
                final_images,
                raw_pages_info,
                cover_asset,
            )
            self.archiver.archive(components, output_path)
            logger.info("EPUBファイルの作成に成功しました: {}", output_path)
            return output_path
        except Exception as e:
            logger.exception("EPUBファイルの作成中に致命的なエラーが発生しました。")
            self._cleanup_failed_build(output_path)
            raise BuildError(f"EPUBのビルドに失敗しました: {e}") from e

    def _create_template_env(self, workspace: Workspace) -> Environment:
        """ワークスペースのプロバイダーに基づいてJinja2環境を生成します。"""
        provider_name = "default"  # フォールバック
        try:
            with open(workspace.manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                provider_name = manifest.get("provider_name", "default")
            logger.debug("Provider '{}' のテーマを使用します。", provider_name)
        except (IOError, json.JSONDecodeError):
            logger.warning(
                "manifest.jsonが読み取れないため、デフォルトテーマを使用します。"
            )

        assets_root = Path(__file__).parent.parent.parent.parent / "assets"
        epub_assets_root = assets_root / "epub"
        provider_template_dir = epub_assets_root / provider_name
        default_template_dir = epub_assets_root / "default"

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
        return Environment(loader=loader, autoescape=True)

    def _determine_output_path(self, metadata: NovelMetadata) -> Path:
        """メタデータと設定に基づき、最終的な出力ファイルパスを決定します。"""
        if metadata.series and self.settings.builder.series_filename_template:
            template = self.settings.builder.series_filename_template
        else:
            template = self.settings.builder.filename_template

        template_vars = {
            "title": metadata.title or "untitled",
            "id": metadata.identifier.novel_id or metadata.identifier.post_id or "0",
            "author_name": metadata.author.name or "unknown_author",
            "author_id": str(metadata.author.id or "0"),
            "series_title": metadata.series.title if metadata.series else "",
            "series_id": str(metadata.series.id if metadata.series else "0"),
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
                logger.info("不完全な出力ファイルを削除しました: {}", path)
        except OSError as e:
            logger.error("出力ファイルの削除に失敗しました: {}, {}", path, e)
