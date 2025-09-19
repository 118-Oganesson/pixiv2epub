#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/orchestration/coordinator.py
#
# このモジュールは、アプリケーションの主要な処理フローを統括する
# Coordinatorクラスを定義します。
# Providerによるデータ取得からBuilderによるファイル生成までの一連の流れを管理します。
# -----------------------------------------------------------------------------
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..builders.base_builder import BaseBuilder
from ..builders.epub.builder import EpubBuilder
from ..providers.base_provider import BaseProvider
from ..providers.pixiv.downloader import PixivProvider


class Coordinator:
    """
    データ取得(Provider)からファイル生成(Builder)までの一連の処理フローを統括するクラス。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Coordinatorのインスタンスを初期化します。

        Args:
            config (Dict[str, Any]): アプリケーション全体の設定情報。
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._providers: Dict[str, Type[BaseProvider]] = {}
        self._builders: Dict[str, Type[BaseBuilder]] = {}
        self._register_components()

    def _register_components(self):
        """
        アプリケーションで利用可能なProviderとBuilderを登録します。
        将来的にはプラグインシステムなどで動的に読み込むことも可能ですが、
        現在は静的に登録しています。
        """
        # Providerの登録
        self.register_provider(PixivProvider.get_provider_name(), PixivProvider)

        # Builderの登録
        self.register_builder(EpubBuilder.get_builder_name(), EpubBuilder)

        self.logger.info(f"Registered providers: {list(self._providers.keys())}")
        self.logger.info(f"Registered builders: {list(self._builders.keys())}")

    def register_provider(self, name: str, provider_class: Type[BaseProvider]):
        """
        新しいProviderクラスをCoordinatorに登録します。

        Args:
            name (str): Providerを識別するための名前 (例: "pixiv")。
            provider_class (Type[BaseProvider]): 登録するProviderクラス。
        """
        self._providers[name] = provider_class
        self.logger.debug(f"Provider '{name}' registered.")

    def register_builder(self, name: str, builder_class: Type[BaseBuilder]):
        """
        新しいBuilderクラスをCoordinatorに登録します。

        Args:
            name (str): Builderを識別するための名前 (例: "epub")。
            builder_class (Type[BaseBuilder]): 登録するBuilderクラス。
        """
        self._builders[name] = builder_class
        self.logger.debug(f"Builder '{name}' registered.")

    def run(
        self,
        target_id: Any,
        target_type: str = "novel",
        provider_name: Optional[str] = None,
        builder_name: Optional[str] = None,
    ) -> List[Path]:
        """
        指定されたIDとタイプに基づいて、ダウンロードからビルドまでの一連の処理を実行します。

        Args:
            target_id (Any): 処理対象のID (小説ID, シリーズID, ユーザーIDなど)。
            target_type (str): 処理の種類 ("novel", "series", "user")。
            provider_name (Optional[str]): 使用するデータプロバイダの名前。Noneの場合、
                登録されているプロバイダが1つであれば自動的に選択されます。
            builder_name (Optional[str]): 使用するビルダーの名前。Noneの場合、
                登録されているビルダーが1つであれば自動的に選択されます。

        Returns:
            List[Path]: 正常に生成されたファイルのパスのリスト。
        """
        # --- ProviderとBuilderの選択 ---
        final_provider_name = self._determine_component_name(
            provider_name, self._providers, "Provider"
        )
        if not final_provider_name:
            return []

        final_builder_name = self._determine_component_name(
            builder_name, self._builders, "Builder"
        )
        if not final_builder_name:
            return []

        self.logger.info(
            f"Starting process: type='{target_type}', id='{target_id}', "
            f"provider='{final_provider_name}', builder='{final_builder_name}'"
        )

        # 1. Providerを選択し、データをダウンロードする
        downloaded_paths = self._execute_download(
            final_provider_name, target_type, target_id
        )
        if not downloaded_paths:
            self.logger.warning("Download phase returned no paths. Halting process.")
            return []
        self.logger.info(f"Successfully downloaded {len(downloaded_paths)} item(s).")

        # 2. Builderを選択し、ダウンロードされたデータからファイルを生成する
        built_files = self._execute_build(final_builder_name, downloaded_paths)
        if not built_files:
            self.logger.warning("Build phase produced no files.")
            return []

        self.logger.info(
            f"Process finished. Successfully built {len(built_files)} file(s)."
        )
        return built_files

    def _determine_component_name(
        self, name: Optional[str], components: Dict[str, Type], component_type: str
    ) -> Optional[str]:
        """
        使用するコンポーネント（Provider/Builder）の名前を決定します。
        名前が指定されていない場合、登録済みのコンポーネントが1つであればそれを自動選択します。
        """
        if name:
            if name in components:
                return name
            else:
                self.logger.error(
                    f"{component_type} '{name}' not found. "
                    f"Available: {list(components.keys())}"
                )
                return None

        if len(components) == 1:
            return list(components.keys())[0]
        elif len(components) == 0:
            self.logger.error(f"No {component_type}s are registered.")
            return None
        else:
            self.logger.error(
                f"{component_type} not specified and multiple are available: "
                f"{list(components.keys())}. Please specify one."
            )
            return None

    def _execute_download(
        self, provider_name: str, target_type: str, target_id: Any
    ) -> List[Path]:
        """
        指定されたProviderを使用してデータのダウンロード処理を実行します。

        Returns:
            List[Path]: ダウンロードされた生データが格納されているディレクトリパスのリスト。
        """
        provider_class = self._providers.get(provider_name)
        if not provider_class:
            self.logger.error(f"Provider '{provider_name}' not found.")
            return []

        try:
            provider = provider_class(self.config)
            download_method = getattr(provider, f"get_{target_type}")
            # get_novelは単一Path、その他はList[Path]を返すため、必ずリストに変換する
            raw_paths = download_method(target_id)
            return [raw_paths] if isinstance(raw_paths, Path) else raw_paths

        except AttributeError:
            self.logger.error(
                f"Invalid target_type '{target_type}' for provider '{provider_name}'. "
                f"Method 'get_{target_type}' not found."
            )
            return []
        except Exception as e:
            self.logger.error(
                f"Error during download phase with provider '{provider_name}': {e}",
                exc_info=True,
            )
            return []

    def _execute_build(self, builder_name: str, source_dirs: List[Path]) -> List[Path]:
        """
        指定されたBuilderを使用してファイルのビルド処理を実行します。

        Args:
            builder_name (str): 使用するビルダーの名前。
            source_dirs (List[Path]): ビルド対象のデータが格納されたディレクトリのリスト。

        Returns:
            List[Path]: 生成されたファイルのパスのリスト。
        """
        builder_class = self._builders.get(builder_name)
        if not builder_class:
            self.logger.error(f"Builder '{builder_name}' not found.")
            return []

        built_files: List[Path] = []
        total = len(source_dirs)
        for i, novel_dir in enumerate(source_dirs, 1):
            self.logger.info(f"--- Building item {i}/{total}: {novel_dir.name} ---")
            try:
                builder = builder_class(novel_dir, self.config)
                output_path = builder.build()
                built_files.append(output_path)
            except Exception as e:
                self.logger.error(
                    f"Failed to build from source '{novel_dir}': {e}", exc_info=True
                )
                # 一つのビルドが失敗しても、次のアイテムの処理を続行する
                continue

        return built_files
