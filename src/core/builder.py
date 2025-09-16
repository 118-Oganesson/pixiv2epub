import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from ..data.models import NovelMetadata
from ..utils.path_manager import PathManager
from .asset_manager import AssetManager
from .component_generator import ComponentGenerator
from .archiver import Archiver


class EpubBuilder:
    """EPUB生成プロセス全体を統括するオーケストレーター。

    AssetManager, ComponentGenerator, Archiverを連携させ、
    小説データから単一のEPUBファイルを生成する責務を持つ。
    """

    def __init__(
        self,
        novel_dir: str,
        config: dict,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        """EpubBuilderのインスタンスを初期化します。

        Args:
            novel_dir (str): 小説のソースファイルが格納されているディレクトリのパス。
            config (dict): アプリケーション全体の設定情報。
            custom_metadata (Optional[Dict[str, Any]]):
                detail.jsonの代わりに用いるメタデータ。Noneの場合、
                novel_dir内のdetail.jsonを読み込みます。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.novel_dir_path = Path(novel_dir).resolve()
        self.config = config

        if custom_metadata:
            # 引数で直接メタデータが渡された場合は、それを優先して使用する
            metadata_dict = custom_metadata
            self.logger.debug("カスタムメタデータを使用してビルダーを初期化します。")
        else:
            detail_json_path = self.novel_dir_path / "detail.json"
            if not detail_json_path.is_file():
                raise FileNotFoundError(
                    f"detail.jsonが見つかりません: {detail_json_path}"
                )
            with open(detail_json_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)

        self.metadata = NovelMetadata.from_dict(metadata_dict)
        novel_directory_name = self.novel_dir_path.name

        self.paths = PathManager(
            base_dir=self.novel_dir_path.parent,
            novel_dir_name=novel_directory_name,
        )

        css_rel_path = self.config.get("builder", {}).get(
            "css_file", "styles/style.css"
        )
        self.asset_manager = AssetManager(self.paths, self.metadata, css_rel_path)
        self.component_generator = ComponentGenerator(
            self.config, self.metadata, self.paths
        )
        self.archiver = Archiver(self.config)

    def create_epub(self) -> Path:
        """EPUBファイルを生成するメインの実行メソッド。

        一連の処理（アセット収集、コンポーネント生成、アーカイブ）を順に実行します。
        処理中にエラーが発生した場合は、不完全な出力ファイルをクリーンアップします。

        Returns:
            Path: 生成されたEPUBファイルのパス。

        Raises:
            Exception: EPUB生成処理中に発生した予期せぬエラー。
        """
        output_path = self._determine_output_path()
        self.logger.debug(f"EPUB作成処理を開始します: {self.novel_dir_path}")
        if output_path.exists():
            self.logger.warning(
                f"出力ファイル {output_path} は既に存在するため、上書きします。"
            )

        try:
            final_images, raw_pages_info, cover_asset = (
                self.asset_manager.gather_assets()
            )

            components = self.component_generator.generate_components(
                final_images, raw_pages_info, cover_asset
            )

            self.archiver.archive(components, output_path)

            self.logger.debug(f"EPUBファイルの作成に成功しました: {output_path}")
            return output_path

        except Exception:
            self.logger.exception(
                "EPUBファイルの作成中に致命的なエラーが発生しました。"
            )
            self._cleanup_failed_build(output_path)
            raise

    def _determine_output_path(self) -> Path:
        """メタデータと設定に基づき、最終的な出力ファイルパスを決定します。

        設定ファイルに定義されたテンプレートを用いてファイル名を生成し、
        ファイルシステムとして無効な文字をサニタイズします。
        また、出力先ディレクトリが存在しない場合は自動的に作成します。

        Returns:
            Path: EPUBの出力先として解決された絶対パス。
        """
        builder_conf = self.config.get("builder", {})

        # シリーズ情報があり、専用テンプレートが設定されていればそれを優先する
        if self.metadata.series and "series_filename_template" in builder_conf:
            template = builder_conf.get("series_filename_template")
        else:
            template = builder_conf.get("filename_template", "{title}.epub")

        template_vars = {
            "title": self.metadata.title or "untitled",
            "id": self.metadata.identifier.get("novel_id", "0"),
            "author_name": self.metadata.authors.name or "unknown_author",
            "author_id": str(self.metadata.authors.id or "0"),
            "series_title": self.metadata.series.title if self.metadata.series else "",
        }

        relative_path_str = template.format(**template_vars)

        # OSでファイル名として使用できない文字をアンダースコアに置換し、安全なパスを確保する
        invalid_chars = r'[\\/:*?"<>|]'
        safe_parts = [
            re.sub(invalid_chars, "_", part) for part in relative_path_str.split("/")
        ]
        safe_relative_path = Path(*safe_parts)

        output_dir_base = Path(builder_conf.get("output_directory", "."))
        final_path = output_dir_base / safe_relative_path

        # 出力先の親ディレクトリが存在しない場合に備え、再帰的に作成する
        final_path.parent.mkdir(parents=True, exist_ok=True)

        return final_path

    def _cleanup_failed_build(self, path: Path):
        """ビルド失敗時に、不完全な出力ファイルを削除します。

        Args:
            path (Path): 削除対象のファイルパス。
        """
        try:
            if path.exists():
                os.remove(path)
                self.logger.info(f"不完全な出力ファイルを削除しました: {path}")
        except OSError as e:
            self.logger.error(f"出力ファイルの削除に失敗しました: {path}, {e}")
