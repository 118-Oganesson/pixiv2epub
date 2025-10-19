# FILE: src/pixiv2epub/infrastructure/providers/base_provider.py
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from pybreaker import CircuitBreaker
from requests.exceptions import RequestException

from ...domain.interfaces import IProvider, IWorkspaceRepository
from ...models.domain import FetchedData
from ...models.workspace import Workspace, WorkspaceManifest
from ...shared.exceptions import ApiError, DataProcessingError
from ...shared.settings import Settings
from .fanbox.content_processor import FanboxContentProcessor
from .fanbox.fetcher import FanboxFetcher
from .pixiv.content_processor import PixivContentProcessor
from .pixiv.fetcher import PixivFetcher


class BaseProvider(IProvider):
    """
    プロバイダーの共通的な振る舞いを定義する抽象基底クラス。
    Template Method パターンを利用して、コンテンツ取得のワークフローを共通化します。
    """

    def __init__(
        self,
        settings: Settings,
        breaker: CircuitBreaker,
        fetcher: "PixivFetcher | FanboxFetcher",
        processor: "PixivContentProcessor | FanboxContentProcessor",
        repository: IWorkspaceRepository,
    ):
        """
        Args:
            settings (Settings): アプリケーション設定。
            breaker (CircuitBreaker): 共有サーキットブレーカーインスタンス。
            fetcher: データ取得を担当するオブジェクト。
            processor: データ処理を担当するオブジェクト。
            repository: ワークスペースの永続化を担当するオブジェクト。
        """
        self.settings = settings
        self.workspace_dir = settings.workspace.root_directory
        self._breaker: CircuitBreaker = breaker
        self.fetcher = fetcher
        self.processor = processor
        self.repository = repository

        logger.bind(provider_name=self.get_provider_name()).info(
            "プロバイダーを初期化しました。"
        )

    @property
    def breaker(self) -> CircuitBreaker:
        """サーキットブレーカーのインスタンスを返します。"""
        return self._breaker

    @classmethod
    def get_provider_name(cls) -> str:
        # このメソッドはサブクラスでオーバーライドされることを期待します。
        raise NotImplementedError

    def get_work(self, content_id: Any) -> Optional[Workspace]:
        """
        単一の作品を取得し、Workspaceを生成して返す共通のワークフロー。
        これが Template Method となります。
        """
        provider_name = self.get_provider_name()
        logger.info(f"{provider_name} の作品処理を開始")
        workspace = self.repository.setup_workspace(content_id, provider_name)

        try:
            # --- 1. データの取得 ---
            # Fetcherは常にFetchedDataオブジェクトを返すという契約
            fetched_data: FetchedData = self.fetcher.fetch_novel_data(content_id)

            # --- 2. 更新のチェック ---
            # 更新チェックには主要データ(primary_data)のみを使用
            update_required, new_content_identifier = self.processor.check_for_updates(
                workspace, fetched_data.primary_data
            )
            if not update_required:
                logger.bind(workspace_id=workspace.id).info(
                    "コンテンツに変更なし、スキップします。"
                )
                return None

            # --- 3. コンテンツの処理とワークスペースへの保存 ---
            # ProcessorにはFetchedDataオブジェクト全体を渡す
            metadata = self.processor.process_and_populate_workspace(
                workspace, fetched_data
            )

            # --- 4. メタデータとマニフェストの永続化 ---
            manifest = WorkspaceManifest(
                provider_name=provider_name,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                source_metadata={"id": content_id},
                content_hash=new_content_identifier,
            )
            self.repository.persist_metadata(workspace, metadata, manifest)

            logger.bind(
                title=metadata.title, workspace_path=str(workspace.root_path)
            ).success("作品データの取得と処理が完了しました。")
            return workspace

        except (RequestException, ApiError) as e:
            raise ApiError(
                f"ID {content_id} のデータ取得に失敗: {e}",
                provider_name,
            ) from e
        except DataProcessingError as e:
            # Processor内で発生したエラーもここで捕捉
            raise DataProcessingError(
                f"ID {content_id} のデータ解析に失敗: {e}",
                provider_name,
            ) from e
