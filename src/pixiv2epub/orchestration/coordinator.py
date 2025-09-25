# src/pixiv2epub/orchestration/coordinator.py

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .. import constants as const
from ..builders.base_builder import BaseBuilder
from ..builders.epub.builder import EpubBuilder
from ..providers.base_provider import BaseProvider
from ..providers.pixiv.provider import PixivProvider


AVAILABLE_PROVIDERS: Dict[str, Type[BaseProvider]] = {"pixiv": PixivProvider}
AVAILABLE_BUILDERS: Dict[str, Type[BaseBuilder]] = {"epub": EpubBuilder}


class Coordinator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_provider(self, provider_name: str) -> BaseProvider:
        provider_class = AVAILABLE_PROVIDERS.get(provider_name)
        if not provider_class:
            raise ValueError(f"不明なプロバイダです: {provider_name}")
        return provider_class(self.config)

    def _get_builder(self, builder_name: str, novel_dir: Path) -> BaseBuilder:
        builder_class = AVAILABLE_BUILDERS.get(builder_name)
        if not builder_class:
            raise ValueError(f"不明なビルダーです: {builder_name}")
        return builder_class(novel_dir=novel_dir, config=self.config)

    def _is_cleanup_enabled(self, cleanup: Optional[bool]) -> bool:
        """クリーンアップが有効かどうかを判定する。"""
        if cleanup is not None:
            return cleanup
        return self.config.get(const.KEY_BUILDER, {}).get("cleanup_after_build", False)

    def _cleanup_empty_parents(self, directory: Path, stop_at: Path):
        """指定されたディレクトリの親を、空であれば再帰的に削除する。"""
        parent = directory.parent
        # ルートダウンロードディレクトリに到達するまで、またはパスの階層関係が崩れたらループを停止
        while (
            parent.is_absolute()
            and parent != stop_at
            and parent.is_relative_to(stop_at)
        ):
            try:
                if not os.listdir(parent):
                    self.logger.info(f"空の親フォルダを削除します: {parent}")
                    os.rmdir(parent)
                    parent = parent.parent
                else:
                    # 親が空でなければ、それ以上遡る必要はない
                    break
            except OSError as e:
                self.logger.warning(
                    f"親フォルダ '{parent.name}' の削除に失敗しました: {e}"
                )
                break

    def _handle_cleanup(self, directory: Path, base_dir: Path, cleanup: Optional[bool]):
        """中間ファイルと、空になった親フォルダを削除する。"""
        if self._is_cleanup_enabled(cleanup):
            try:
                self.logger.info(f"中間ファイルを削除します: {directory}")
                shutil.rmtree(directory)
                # 削除後、空になった親フォルダのクリーンアップを試みる
                self._cleanup_empty_parents(directory, stop_at=base_dir)
            except OSError as e:
                self.logger.error(f"中間ファイルの削除に失敗しました: {e}")

    def download_and_build_novel(
        self,
        provider_name: str,
        builder_name: str,
        novel_id: Any,
        cleanup: Optional[bool] = None,
    ) -> Path:
        self.logger.info(f"小説ID: {novel_id} の処理を開始します...")
        provider = self._get_provider(provider_name)
        downloaded_path = provider.get_novel(novel_id)

        builder = self._get_builder(builder_name, downloaded_path)
        output_path = builder.build()

        self._handle_cleanup(downloaded_path, provider.base_dir, cleanup)

        self.logger.info(f"処理が正常に完了しました: {output_path}")
        return output_path

    def download_and_build_series(
        self,
        provider_name: str,
        builder_name: str,
        series_id: Any,
        cleanup: Optional[bool] = None,
    ) -> List[Path]:
        self.logger.info(f"シリーズID: {series_id} の処理を開始します...")
        provider = self._get_provider(provider_name)
        downloaded_paths = provider.get_series(series_id)

        output_paths = []
        for path in downloaded_paths:
            try:
                builder = self._get_builder(builder_name, path)
                output_path = builder.build()
                output_paths.append(output_path)
                self._handle_cleanup(path, provider.base_dir, cleanup)
            except Exception as e:
                self.logger.error(
                    f"{path.name} のビルドに失敗しました: {e}", exc_info=True
                )

        self.logger.info(
            f"シリーズ処理完了。{len(output_paths)}/{len(downloaded_paths)}件成功。"
        )
        return output_paths

    def download_and_build_user_novels(
        self,
        provider_name: str,
        builder_name: str,
        user_id: Any,
        cleanup: Optional[bool] = None,
    ) -> List[Path]:
        self.logger.info(f"ユーザーID: {user_id} の全作品の処理を開始します...")
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
                self._handle_cleanup(path, provider.base_dir, cleanup)
            except Exception as e:
                self.logger.error(
                    f"{path.name} のビルドに失敗しました: {e}", exc_info=True
                )

        self.logger.info(f"ユーザー作品処理完了。{len(output_paths)}/{total}件成功。")
        return output_paths
