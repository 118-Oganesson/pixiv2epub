#
# -----------------------------------------------------------------------------
# src/pixiv2epub/builders/epub/builder.py
#
# EPUB生成プロセス全体を統括するオーケストレーター。
#
# AssetManager, EpubGenerator, Archiverを連携させ、
# 小説データから単一のEPUBファイルを生成する責務を持つ。
# -----------------------------------------------------------------------------
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from ..base_builder import BaseBuilder
from .asset_manager import AssetManager
from .generator import EpubGenerator
from .archiver import Archiver
from ...constants import (
    KEY_BUILDER,
    KEY_OUTPUT_DIRECTORY,
    KEY_SERIES_FILENAME_TEMPLATE,
    KEY_FILENAME_TEMPLATE,
    KEY_CSS_FILE,
    INVALID_PATH_CHARS_REGEX,
    DEFAULT_EPUB_FILENAME_TEMPLATE,
)


class EpubBuilder(BaseBuilder):
    """EPUB生成プロセスを統括するクラス。"""

    def __init__(
        self,
        novel_dir: Path,
        config: Dict[str, Any],
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        EpubBuilderのインスタンスを初期化します。

        Args:
            novel_dir (Path): 小説のソースファイルが格納されているディレクトリのパス。
            config (dict): アプリケーション全体の設定情報。
            custom_metadata (Optional[Dict[str, Any]]):
                detail.jsonの代わりに用いるメタデータ。
        """
        super().__init__(novel_dir, config, custom_metadata)

        builder_conf = self.config.get(KEY_BUILDER, {})
        css_rel_path = builder_conf.get(KEY_CSS_FILE)

        # CSSファイルの絶対パスを解決
        self.css_abs_path: Optional[Path] = None
        if css_rel_path:
            # 1. novel_dir内に存在するかチェック
            if (self.novel_dir / css_rel_path).is_file():
                self.css_abs_path = self.novel_dir / css_rel_path
            # 2. カレントディレクトリからの相対パスとしてチェック
            elif Path(css_rel_path).is_file():
                self.css_abs_path = Path(css_rel_path).resolve()
            else:
                self.logger.warning(
                    f"指定されたCSSファイルが見つかりません: {css_rel_path}"
                )

        template_dir = (
            Path.cwd() / "templates"
        )  # プロジェクトルートからの相対パスを想定

        self.asset_manager = AssetManager(self.paths, self.metadata, self.css_abs_path)
        self.generator = EpubGenerator(
            self.config, self.metadata, self.paths, template_dir
        )
        self.archiver = Archiver(self.config)

    @classmethod
    def get_builder_name(cls) -> str:
        """ビルダーの名前として "epub" を返します。"""
        return "epub"

    def build(self) -> Path:
        """
        EPUBファイルを生成するメインの実行メソッド。

        Returns:
            Path: 生成されたEPUBファイルのパス。
        """
        output_path = self._determine_output_path()
        self.logger.info(f"EPUB作成処理を開始します: {self.novel_dir.name}")
        if output_path.exists():
            self.logger.warning(
                f"出力ファイル {output_path} は既に存在するため、上書きします。"
            )

        try:
            # 1. アセット（画像など）を収集
            final_images, raw_pages_info, cover_asset = (
                self.asset_manager.gather_assets()
            )

            # 2. EPUBの構成要素（XHTML, OPFなど）を生成
            components = self.generator.generate_components(
                final_images, raw_pages_info, cover_asset, self.css_abs_path
            )

            # 3. 全てのコンポーネントをZIPに固めて.epubファイルを生成
            self.archiver.archive(components, output_path)

            self.logger.info(f"EPUBファイルの作成に成功しました: {output_path}")
            return output_path

        except Exception:
            self.logger.exception(
                "EPUBファイルの作成中に致命的なエラーが発生しました。"
            )
            self._cleanup_failed_build(output_path)
            raise

    def _determine_output_path(self) -> Path:
        """メタデータと設定に基づき、最終的な出力ファイルパスを決定します。"""
        builder_conf = self.config.get(KEY_BUILDER, {})

        if self.metadata.series and KEY_SERIES_FILENAME_TEMPLATE in builder_conf:
            template = builder_conf[KEY_SERIES_FILENAME_TEMPLATE]
        else:
            template = builder_conf.get(
                KEY_FILENAME_TEMPLATE, DEFAULT_EPUB_FILENAME_TEMPLATE
            )

        template_vars = {
            "title": self.metadata.title or "untitled",
            "id": self.metadata.identifier.get("novel_id", "0"),
            "author_name": self.metadata.authors.name or "unknown_author",
            "author_id": str(self.metadata.authors.id or "0"),
            "series_title": self.metadata.series.title if self.metadata.series else "",
            "series_id": self.metadata.series.id if self.metadata.series else "0",
        }

        relative_path_str = template.format(**template_vars)

        safe_parts = [
            re.sub(INVALID_PATH_CHARS_REGEX, "_", part)
            for part in Path(relative_path_str).parts
        ]
        safe_relative_path = Path(*safe_parts)

        output_dir_base = Path(builder_conf.get(KEY_OUTPUT_DIRECTORY, "./epubs"))
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
