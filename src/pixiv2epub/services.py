# FILE: src/pixiv2epub/services.py
import shutil
from pathlib import Path

from jinja2 import TemplateError
from loguru import logger

from .domain.interfaces import IBuilder, IProvider, IWorkspaceRepository
from .models.workspace import Workspace
from .shared.constants import MANIFEST_FILE_NAME
from .shared.enums import Provider as ProviderEnum
from .shared.exceptions import (
    AssetMissingError,
    BuildError,
    ContentNotFoundError,
    ProviderError,
)
from .shared.settings import Settings
from .utils.url_parser import parse_content_identifier


class ApplicationService:
    """
    アプリケーションの全ユースケースを統括するサービスレイヤー。
    依存関係の構築(DI)はコンポジションルート(cli.py)で行われ、
    このクラスは注入された依存関係を利用してビジネスロジックを実行する責務を持つ。
    """

    def __init__(
        self,
        settings: Settings,
        builder: IBuilder,
        repository: IWorkspaceRepository,
        providers: dict[ProviderEnum, IProvider],
    ):
        self.settings = settings
        self.builder = builder
        self.repository = repository
        self.providers = providers
        logger.debug('ApplicationService が初期化されました。')

    def _get_provider(self, provider_enum: ProviderEnum) -> IProvider:
        """指定されたProviderEnumに対応するIProviderインスタンスを取得します。"""
        provider = self.providers.get(provider_enum)
        if not provider:
            raise ProviderError(
                f'サポートされていないプロバイダーです: {provider_enum.name}',
                provider_name=provider_enum.name,
            )
        return provider

    def run_from_input(self, input_str: str) -> list[Path]:
        """
        単一の入力(URLやID)からダウンロードとビルドの両方を実行します。
        (旧 DownloadBuildOrchestrator.run_from_input の責務)
        """
        provider_enum, content_type, identifier = parse_content_identifier(input_str)
        provider = self._get_provider(provider_enum)

        with logger.contextualize(
            provider=provider_enum.name,
            content_type=content_type.name,
            identifier=str(identifier),
        ):
            logger.info('データ取得処理を開始')
            workspaces = provider.get_works(identifier, content_type)

            logger.info('ダウンロードとビルド処理を開始')
            return self._build_workspaces(
                workspaces, f'{content_type.name.capitalize()}'
            )

    def download_from_input(self, input_str: str) -> list[Path]:
        """
        単一の入力(URLやID)からダウンロードのみを実行します。
        (旧 DownloadBuildOrchestrator.run_from_input(download_only=True) の責務)
        """
        provider_enum, content_type, identifier = parse_content_identifier(input_str)
        provider = self._get_provider(provider_enum)

        with logger.contextualize(
            provider=provider_enum.name,
            content_type=content_type.name,
            identifier=str(identifier),
        ):
            logger.info('データ取得処理(ダウンロードのみ)を開始')
            workspaces = provider.get_works(identifier, content_type)

            logger.bind(download_count=len(workspaces)).success(
                'ダウンロード処理が完了しました。'
            )
            return []

    def build_from_workspaces(self, base_path: Path) -> list[Path]:
        """
        指定されたパス(単一のワークスペースまたはコンテナディレクトリ)から
        EPUBをビルドします。
        (旧 app.Application.build_from_workspace + cli.build の責務)
        """
        workspaces_to_build: list[Path] = []

        try:
            # 1. base_pathが単一のワークスペースか検証
            Workspace.from_path(base_path)
            workspaces_to_build.append(base_path)
        except ValueError:
            # 2. 検証失敗なら、再帰的に検索
            logger.bind(search_path=str(base_path)).info(
                'ビルド可能なワークスペースを再帰的に検索します...'
            )
            for manifest_path in base_path.rglob(MANIFEST_FILE_NAME):
                workspaces_to_build.append(manifest_path.parent)

        if not workspaces_to_build:
            logger.bind(search_path=str(base_path)).warning(
                'ビルド可能なワークスペースが見つかりませんでした。'
            )
            return []

        total = len(workspaces_to_build)
        logger.bind(count=total).info('✅ ビルド対象ワークスペースが見つかりました。')

        built_paths: list[Path] = []
        for i, path in enumerate(workspaces_to_build, 1):
            log = logger.bind(
                current=i,
                total=total,
                workspace_name=path.name,
                workspace_path=str(path),
            )
            log.info('--- ビルド処理を開始 ---')
            try:
                # (旧 app.Application.build_from_workspace のロジック)
                workspace = Workspace.from_path(path)
                output_path = self.builder.build(workspace)

                log.bind(output_path=str(output_path)).success('ビルド成功')
                built_paths.append(output_path)

            except AssetMissingError as e:
                log.bind(error=str(e)).error('❌ ビルドに必要なアセットがありません。')
            except Exception as e:
                log.bind(error=str(e)).error(
                    '❌ ビルドに失敗しました。',
                    exc_info=self.settings.log_level == 'DEBUG',
                )
            finally:
                log.info('---')

        logger.bind(success_count=len(built_paths), total=total).info(
            '✨ 全てのビルド処理が完了しました。'
        )
        return built_paths

    # --- プライベートヘルパー (旧Orchestratorから移植) ---

    def _is_cleanup_enabled(self) -> bool:
        """クリーンアップが有効かどうかを判定する。"""
        return self.settings.builder.cleanup_after_build

    def _handle_cleanup(self, workspace: Workspace) -> None:
        """中間ファイル(ワークスペース)を削除する。"""
        if self._is_cleanup_enabled():
            log = logger.bind(workspace_path=str(workspace.root_path))
            try:
                log.info('ワークスペースのクリーンアップを開始')
                shutil.rmtree(workspace.root_path)
            except OSError as e:
                log.bind(error=str(e)).error('ワークスペースのクリーンアップ失敗')

    def _build_workspaces(
        self,
        workspaces: list[Workspace],
        collection_type: str,
    ) -> list[Path]:
        """作品群を処理するための共通ロジック。"""

        if not workspaces:
            logger.warning('処理対象の作品が見つかりませんでした。')
            return []

        output_paths: list[Path] = []
        total = len(workspaces)
        logger.bind(total_works=total).info(f'{collection_type} のビルドを開始')

        for i, workspace in enumerate(workspaces, 1):
            try:
                provider_name, identifier = 'unknown', 'unknown'
                try:
                    # workspace.id (例: "pixiv_12345") から分割
                    provider_name, identifier = workspace.id.split('_', 1)
                except ValueError:
                    logger.warning(
                        f"ワークスペースID '{workspace.id}' の形式が不正です。"
                    )

                with logger.contextualize(
                    workspace_id=workspace.id,
                    provider=provider_name,
                    identifier=identifier,
                ):
                    logger.bind(current_work=i, total_works=total).info(
                        '個別作品の処理を開始'
                    )
                    output_path = self.builder.build(workspace)
                    output_paths.append(output_path)
            except ContentNotFoundError as e:
                logger.bind(reason=str(e)).warning('コンテンツが見つからずスキップ')
                continue
            except (BuildError, ProviderError) as e:
                logger.bind(workspace_id=workspace.id, error=str(e)).error(
                    'ワークスペースの処理失敗',
                    exc_info=self.settings.log_level == 'DEBUG',
                )
            # テンプレートエラーを個別に捕捉
            except TemplateError as e:
                template_name = getattr(e, 'name', 'N/A')
                logger.bind(
                    workspace_id=workspace.id, template_name=template_name
                ).error(
                    f"テンプレート '{template_name}' のレンダリングに失敗しました。",
                    exc_info=True,  # スタックトレースを出力
                )
            # 予期せぬエラーは .exception() でスタックトレースを記録
            except Exception:
                logger.bind(workspace_id=workspace.id).exception(
                    'ワークスペース処理中に予期せぬエラー発生'
                )
            finally:
                if workspace:
                    self._handle_cleanup(workspace)

        logger.bind(success_count=len(output_paths), total_works=total).success(
            f'{collection_type} の処理完了'
        )
        return output_paths
