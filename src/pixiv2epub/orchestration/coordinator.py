#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/orchestration/coordinator.py
#
# ProviderとBuilderを連携させ、ダウンロードからビルドまでの一連の処理フローを
# 統括するオーケストレーター。
# -----------------------------------------------------------------------------
import logging
from pathlib import Path
from typing import Any, Dict, List, Type

from ..providers.base_provider import BaseProvider
from ..providers.pixiv.provider import PixivProvider
from ..builders.base_builder import BaseBuilder
from ..builders.epub.builder import EpubBuilder

# 将来の拡張性を考慮し、利用可能なクラスを辞書で管理
AVAILABLE_PROVIDERS: Dict[str, Type[BaseProvider]] = {"pixiv": PixivProvider}
AVAILABLE_BUILDERS: Dict[str, Type[BaseBuilder]] = {"epub": EpubBuilder}


class Coordinator:
    """ダウンロードとビルドのプロセス全体を調整・実行するクラス。"""

    def __init__(self, config: Dict[str, Any]):
        """
        Coordinatorを初期化します。

        Args:
            config (Dict[str, Any]): アプリケーション全体の設定。
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_provider(self, provider_name: str) -> BaseProvider:
        """指定された名前のProviderインスタンスを生成して返します。"""
        provider_class = AVAILABLE_PROVIDERS.get(provider_name)
        if not provider_class:
            raise ValueError(f"不明なプロバイダです: {provider_name}")
        return provider_class(self.config)

    def _get_builder(self, builder_name: str, novel_dir: Path) -> BaseBuilder:
        """指定された名前のBuilderインスタンスを生成して返します。"""
        builder_class = AVAILABLE_BUILDERS.get(builder_name)
        if not builder_class:
            raise ValueError(f"不明なビルダーです: {builder_name}")
        return builder_class(novel_dir=novel_dir, config=self.config)

    def download_and_build_novel(
        self, provider_name: str, builder_name: str, novel_id: Any
    ) -> Path:
        """単一の小説をダウンロードし、指定されたフォーマットでビルドします。"""
        self.logger.info(
            f"小説ID: {novel_id} の処理を開始します... (Provider: {provider_name}, Builder: {builder_name})"
        )
        provider = self._get_provider(provider_name)
        downloaded_path = provider.get_novel(novel_id)

        builder = self._get_builder(builder_name, downloaded_path)
        output_path = builder.build()
        self.logger.info(f"処理が正常に完了しました: {output_path}")
        return output_path

    def download_and_build_series(
        self, provider_name: str, builder_name: str, series_id: Any
    ) -> List[Path]:
        """シリーズをダウンロードし、含まれる各小説を指定のフォーマットでビルドします。"""
        self.logger.info(
            f"シリーズID: {series_id} の処理を開始します... (Provider: {provider_name}, Builder: {builder_name})"
        )
        provider = self._get_provider(provider_name)
        downloaded_paths = provider.get_series(series_id)

        output_paths = []
        for path in downloaded_paths:
            try:
                builder = self._get_builder(builder_name, path)
                output_path = builder.build()
                output_paths.append(output_path)
            except Exception as e:
                self.logger.error(
                    f"{path.name} のビルドに失敗しました: {e}", exc_info=True
                )

        self.logger.info(
            f"シリーズ処理が完了しました。 {len(output_paths)}/{len(downloaded_paths)} 件成功。"
        )
        return output_paths

    def download_and_build_user_novels(
        self, provider_name: str, builder_name: str, user_id: Any
    ) -> List[Path]:
        """
        特定のユーザーの全小説をダウンロードし、それぞれを指定されたフォーマットでビルドします。

        Args:
            provider_name (str): 使用するプロバイダ名 (例: "pixiv")。
            builder_name (str): 使用するビルダー名 (例: "epub")。
            user_id (Any): 処理対象のユーザーID。

        Returns:
            List[Path]: 生成されたファイルのパスのリスト。
        """
        self.logger.info(
            f"ユーザーID: {user_id} の全作品の処理を開始します... (Provider: {provider_name}, Builder: {builder_name})"
        )
        provider = self._get_provider(provider_name)
        downloaded_paths = provider.get_user_novels(user_id)

        output_paths = []
        total = len(downloaded_paths)
        self.logger.info(f"合計 {total} 件の作品をビルドします。")

        for i, path in enumerate(downloaded_paths, 1):
            try:
                self.logger.info(f"--- Processing {i}/{total}: {path.name} ---")
                builder = self._get_builder(builder_name, path)
                output_path = builder.build()
                output_paths.append(output_path)
            except Exception as e:
                self.logger.error(
                    f"{path.name} のビルドに失敗しました: {e}", exc_info=True
                )

        self.logger.info(
            f"ユーザー作品の処理が完了しました。 {len(output_paths)}/{total} 件成功。"
        )
        return output_paths
