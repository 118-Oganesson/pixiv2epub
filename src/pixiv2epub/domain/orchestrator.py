# FILE: src/pixiv2epub/domain/orchestrator.py
import shutil
from pathlib import Path
from typing import List

from loguru import logger
from jinja2 import TemplateError

from ..domain.interfaces import IBuilder, IProviderFactory
from ..models.workspace import Workspace
from ..shared.exceptions import BuildError, ContentNotFoundError, ProviderError
from ..shared.settings import Settings
from ..utils.url_parser import parse_content_identifier


class DownloadBuildOrchestrator:
    """
    データ取得(Provider)と成果物生成(Builder)のワークフローを調整する責務を持つ。
    アプリケーションの主要なユースケースを実装します。
    """

    def __init__(
        self,
        builder: IBuilder,
        settings: Settings,
        provider_factory: IProviderFactory,
    ):
        self.builder = builder
        self.settings = settings
        self.provider_factory = provider_factory

    def run_from_input(self, input_str: str, download_only: bool = False) -> List[Path]:
        """
        単一の入力（URLやID）から適切な処理を判断し、実行する。
        """
        provider_enum, content_type, identifier = parse_content_identifier(input_str)
        provider = self.provider_factory.create(provider_enum)

        with logger.contextualize(
            provider=provider_enum.name,
            content_type=content_type.name,
            identifier=str(identifier),
        ):
            logger.info("データ取得処理を開始")
            workspaces = provider.get_works(identifier, content_type)

            if download_only:
                logger.bind(download_count=len(workspaces)).success(
                    "ダウンロード処理が完了しました。"
                )
                return []
            else:
                logger.info("ダウンロードとビルド処理を開始")
                return self._build_workspaces(
                    workspaces, f"{content_type.name.capitalize()}"
                )

    def _is_cleanup_enabled(self) -> bool:
        """クリーンアップが有効かどうかを判定する。"""
        return self.settings.builder.cleanup_after_build

    def _handle_cleanup(self, workspace: Workspace):
        """中間ファイル（ワークスペース）を削除する。"""
        if self._is_cleanup_enabled():
            log = logger.bind(workspace_path=str(workspace.root_path))
            try:
                log.info("ワークスペースのクリーンアップを開始")
                shutil.rmtree(workspace.root_path)
            except OSError as e:
                log.bind(error=str(e)).error("ワークスペースのクリーンアップ失敗")

    def _build_workspaces(
        self,
        workspaces: List[Workspace],
        collection_type: str,
    ) -> List[Path]:
        """作品群を処理するための共通ロジック。"""

        if not workspaces:
            logger.warning("処理対象の作品が見つかりませんでした。")
            return []

        output_paths: List[Path] = []
        total = len(workspaces)
        logger.bind(total_works=total).info(f"{collection_type} のビルドを開始")

        for i, workspace in enumerate(workspaces, 1):
            try:
                with logger.contextualize(workspace_id=workspace.id):
                    logger.bind(current_work=i, total_works=total).info(
                        "個別作品の処理を開始"
                    )
                    output_path = self.builder.build(workspace)
                    output_paths.append(output_path)
            except ContentNotFoundError as e:
                logger.bind(reason=str(e)).warning("コンテンツが見つからずスキップ")
                continue
            except (BuildError, ProviderError) as e:
                logger.bind(workspace_id=workspace.id, error=str(e)).error(
                    "ワークスペースの処理失敗",
                    exc_info=self.settings.log_level == "DEBUG",
                )
            # 修正: テンプレートエラーを個別に捕捉
            except TemplateError as e:
                logger.bind(workspace_id=workspace.id, template_name=e.name).error(
                    f"テンプレート '{e.name}' のレンダリングに失敗しました。",
                    exc_info=True,  # スタックトレースを出力
                )
            # 修正: 予期せぬエラーは .exception() でスタックトレースを記録
            except Exception:
                logger.bind(workspace_id=workspace.id).exception(
                    "ワークスペース処理中に予期せぬエラー発生"
                )
            finally:
                if workspace:
                    self._handle_cleanup(workspace)

        logger.bind(success_count=len(output_paths), total_works=total).success(
            f"{collection_type} の処理完了"
        )
        return output_paths
