# FILE: src/pixiv2epub/infrastructure/builders/epub/builder.py
import json
import os
from pathlib import Path
from typing import Any, cast

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    TemplateError,
)
from loguru import logger

from ....models.domain import UnifiedContentManifest
from ....models.workspace import Workspace
from ....shared.constants import WORKSPACE_PATHS
from ....shared.exceptions import BuildError
from ....shared.settings import Settings
from ....shared.themes import (
    DEFAULT_THEME,
    Theme,
    get_theme_config,
)
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
        return 'epub'

    def build(self, workspace: Workspace) -> Path:
        """EPUBファイルを生成するメインの実行メソッド。"""
        manifest = self._load_metadata(workspace)
        output_path = self._determine_output_path(manifest)

        log = logger.bind(workspace_id=workspace.id, output_path=str(output_path))
        log.info('EPUB作成処理を開始')

        if output_path.exists():
            log.warning('出力ファイルは既に存在するため上書きします。')

        try:
            template_env, theme = self._create_template_env(workspace)
            asset_manager = AssetManager(workspace, manifest)
            generator = EpubComponentGenerator(manifest, workspace, template_env, theme)

            final_images, cover_asset = asset_manager.gather_assets()

            components = generator.generate_components(
                final_images,
                cover_asset,
            )
            self.archiver.archive(components, output_path)
            log.success('EPUBファイルの作成成功')
            return output_path
        except TemplateError as e:
            template_name = getattr(e, 'name', 'N/A')
            logger.bind(template_name=template_name).error(
                f"テンプレート '{template_name}' のレンダリングに失敗しました。",
                exc_info=True,
            )
            self._cleanup_failed_build(output_path)
            raise BuildError(f'テンプレートエラー: {e}') from e
        except Exception as e:
            logger.exception('EPUBファイルの作成中に予期せぬエラーが発生しました。')
            self._cleanup_failed_build(output_path)
            raise BuildError(f'EPUBのビルドに失敗しました: {e}') from e

    def _get_provider_name_from_manifest(self, workspace: Workspace) -> str:
        """(ヘルパー関数に分離) マニフェストからプロバイダ名を安全に読み取る"""
        try:
            with open(workspace.manifest_path, encoding='utf-8') as f:
                manifest_data = cast(dict[str, Any], json.load(f))
            provider_name = manifest_data.get('provider_name', DEFAULT_THEME.name)
            return cast(str, provider_name)
        except (OSError, json.JSONDecodeError):
            logger.bind(workspace_path=str(workspace.root_path)).warning(
                f"'{WORKSPACE_PATHS.MANIFEST_FILE_NAME}'が読み取れないため、デフォルトテーマを使用します。"
            )
            return DEFAULT_THEME.name

    def _create_template_env(self, workspace: Workspace) -> tuple[Environment, Theme]:
        """
        Jinja2環境と、使用するThemeオブジェクトのタプルを生成します。
        (ComponentGeneratorがThemeを必要とするため、タプルで返す)
        """
        provider_name = self._get_provider_name_from_manifest(workspace)
        theme = get_theme_config(provider_name)

        logger.bind(provider_name=provider_name, theme=theme.name).debug(
            'プロバイダーのテーマを使用します。'
        )
        loaders = []
        if theme.name != DEFAULT_THEME.name and theme.path.is_dir():
            loaders.append(FileSystemLoader(str(theme.path)))

        if DEFAULT_THEME.path.is_dir():
            loaders.append(FileSystemLoader(str(DEFAULT_THEME.path)))
        else:
            raise BuildError(
                f'デフォルトのテンプレートディレクトリが見つかりません: {DEFAULT_THEME.path}'
            )
        loader = ChoiceLoader(loaders)
        env = Environment(loader=loader, autoescape=True)
        env.globals['strings'] = theme.strings
        return env, theme

    def _determine_output_path(self, manifest: UnifiedContentManifest) -> Path:
        """メタデータと設定に基づき、最終的な出力ファイルパスを決定します。"""
        core = manifest.core

        if core.isPartOf and self.settings.builder.series_filename_template:
            template = self.settings.builder.series_filename_template
        else:
            template = self.settings.builder.filename_template

        # tag: URI からIDを抽出
        content_id = core.id_.split(':')[-1]
        author_id = core.author.identifier.split(':')[-1]
        series_id_str = str(
            core.isPartOf.identifier.split(':')[-1] if core.isPartOf else '0'
        )

        template_vars = {
            'title': core.name or 'untitled',
            'id': content_id,
            'author_name': core.author.name or 'unknown_author',
            'author_id': author_id or '0',
            'series_title': core.isPartOf.name if core.isPartOf else '',
            'series_id': series_id_str,
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

    def _cleanup_failed_build(self, path: Path) -> None:
        """ビルド失敗時に、不完全な出力ファイルを削除します。"""
        try:
            if path.exists():
                os.remove(path)
            logger.bind(file_path=str(path)).info(
                '不完全な出力ファイルを削除しました。'
            )
        except OSError as e:
            logger.bind(file_path=str(path), error=str(e)).error(
                '出力ファイルの削除に失敗しました。'
            )
