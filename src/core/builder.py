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
    """EPUB生成プロセス全体を統括するオーケストレータークラス。"""

    def __init__(
        self,
        novel_dir: str,
        config: dict,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.novel_dir_path = Path(novel_dir).resolve()
        self.config = config

        if custom_metadata:
            # 外部から渡されたメタデータを使用
            metadata_dict = custom_metadata
            self.logger.debug("カスタムメタデータを使用してビルダーを初期化します。")
        else:
            # 従来通り detail.json を読み込む
            detail_json_path = self.novel_dir_path / "detail.json"
            if not detail_json_path.is_file():
                raise FileNotFoundError(
                    f"detail.jsonが見つかりません: {detail_json_path}"
                )
            with open(detail_json_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)

        self.metadata = NovelMetadata.from_dict(metadata_dict)
        # self.novel_dir_path は Path オブジェクトなので、.name でディレクトリ名を取得
        novel_directory_name = self.novel_dir_path.name

        self.paths = PathManager(
            base_dir=self.novel_dir_path.parent,
            # 'novel_title' と 'novel_id' の代わりに 'novel_dir_name' を使用
            novel_dir_name=novel_directory_name,
        )

        # 2. 専門家クラスのインスタンス化
        css_rel_path = self.config.get("builder", {}).get(
            "css_file", "styles/style.css"
        )
        self.asset_manager = AssetManager(self.paths, self.metadata, css_rel_path)
        self.component_generator = ComponentGenerator(
            self.config, self.metadata, self.paths
        )
        self.archiver = Archiver(self.config)

    def create_epub(self) -> Path:
        """EPUBファイルを作成するメインメソッド。"""
        output_path = self._determine_output_path()
        self.logger.debug(f"EPUB作成処理を開始します: {self.novel_dir_path}")
        if output_path.exists():
            self.logger.warning(
                f"出力ファイル {output_path} は既に存在するため、上書きします。"
            )

        try:
            # 3. 専門家に順番に処理を依頼
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
        """メタデータと設定から最終的な出力ファイルパスを決定します。"""
        builder_conf = self.config.get("builder", {})
        template = builder_conf.get("filename_template", "{title}.epub")

        # テンプレート用の変数を準備 (キーが存在しない場合もエラーにならないように)
        template_vars = {
            "title": self.metadata.title or "untitled",
            "id": self.metadata.identifier.get("novel_id", "0"),
            "author_name": self.metadata.authors.name or "unknown_author",
            "author_id": str(self.metadata.authors.id or "0"),
            "series_title": self.metadata.series.title if self.metadata.series else "",
        }

        # テンプレートを適用してファイル名を生成
        epub_filename = template.format(**template_vars)

        # ファイル名として不正な文字を置換または削除
        invalid_chars = r'[\\/:*?"<>|]'
        safe_filename = re.sub(invalid_chars, "_", epub_filename)

        output_dir_str = builder_conf.get("output_directory", ".")
        path = Path(output_dir_str)
        path.mkdir(parents=True, exist_ok=True)
        return path / safe_filename

    def _cleanup_failed_build(self, path: Path):
        """ビルド失敗時に、不完全な出力ファイルを削除します。"""
        try:
            if path.exists():
                os.remove(path)
                self.logger.info(f"不完全な出力ファイルを削除しました: {path}")
        except OSError as e:
            self.logger.error(f"出力ファイルの削除に失敗しました: {path}, {e}")
