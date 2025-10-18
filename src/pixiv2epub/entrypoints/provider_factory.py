# FILE: src/pixiv2epub/entrypoints/provider_factory.py

from typing import Dict, Type
from pybreaker import CircuitBreaker

from ..domain.interfaces import IProvider, IWorkspaceRepository
from ..infrastructure.providers.fanbox.provider import FanboxProvider
from ..infrastructure.providers.pixiv.provider import PixivProvider
from ..shared.enums import Provider as ProviderEnum
from ..shared.settings import Settings
from ..infrastructure.providers.pixiv.client import PixivApiClient
from ..infrastructure.providers.pixiv.downloader import (
    ImageDownloader as PixivImageDownloader,
)
from ..infrastructure.providers.fanbox.client import FanboxApiClient
from ..infrastructure.providers.fanbox.downloader import (
    FanboxImageDownloader,
)
from ..infrastructure.repositories.filesystem import FileSystemWorkspaceRepository
from ..infrastructure.providers.pixiv.fetcher import PixivFetcher
from ..infrastructure.providers.pixiv.content_processor import PixivContentProcessor
from ..infrastructure.providers.fanbox.fetcher import FanboxFetcher
from ..infrastructure.providers.fanbox.content_processor import FanboxContentProcessor
from ..infrastructure.strategies.mappers import (
    PixivMetadataMapper,
    FanboxMetadataMapper,
)
from ..infrastructure.strategies.parsers import PixivTagParser, FanboxBlockParser
from ..infrastructure.strategies.update_checkers import (
    ContentHashUpdateStrategy,
    TimestampUpdateStrategy,
)


class ProviderFactory:
    """
    ProviderEnum に基づいて、対応する具象 Provider クラスのインスタンスを生成します。
    依存関係の注入（ApiClient, Downloader）もこのファクトリが担当します。
    """

    def __init__(self, settings: Settings):
        # IProviderを実装した具象クラスを登録します
        self._providers: Dict[ProviderEnum, Type[IProvider]] = {
            ProviderEnum.PIXIV: PixivProvider,
            ProviderEnum.FANBOX: FanboxProvider,
        }
        self._settings = settings

        # ファクトリで共有サーキットブレーカーを_一度だけ_作成する
        self._shared_breaker = CircuitBreaker(
            fail_max=self._settings.downloader.circuit_breaker.fail_max,
            reset_timeout=self._settings.downloader.circuit_breaker.reset_timeout,
        )

        # ワークスペースリポジトリも一度だけ作成する
        self._repository: IWorkspaceRepository = FileSystemWorkspaceRepository(
            self._settings.workspace
        )

    def create(self, provider_type: ProviderEnum) -> IProvider:
        """指定された種類のProviderインスタンスを生成し、依存関係を注入して返します。"""
        provider_class = self._providers.get(provider_type)
        if not provider_class:
            raise ValueError(
                f"サポートされていないプロバイダーです: {provider_type.name}"
            )

        # --- 依存関係の組み立てロジック ---
        try:
            if provider_type == ProviderEnum.PIXIV:
                # 1. 依存オブジェクトの作成
                api_client = PixivApiClient(
                    breaker=self._shared_breaker,
                    provider_name=provider_class.get_provider_name(),
                    auth_settings=self._settings.providers.pixiv,
                    api_delay=self._settings.downloader.api_delay,
                    api_retries=self._settings.downloader.api_retries,
                )
                downloader = PixivImageDownloader(
                    api_client=api_client,
                    overwrite=self._settings.downloader.overwrite_existing_images,
                )
                fetcher = PixivFetcher(api_client=api_client)
                processor = PixivContentProcessor(
                    parser=PixivTagParser(),
                    mapper=PixivMetadataMapper(),
                    downloader=downloader,
                    update_checker=ContentHashUpdateStrategy(),
                )

                # 2. Providerに依存を注入して返す
                return provider_class(
                    settings=self._settings,
                    api_client=api_client,
                    breaker=self._shared_breaker,
                    fetcher=fetcher,
                    processor=processor,
                    repository=self._repository,
                )

            elif provider_type == ProviderEnum.FANBOX:
                # 1. Fanbox用のApiClientを作成
                api_client = FanboxApiClient(
                    breaker=self._shared_breaker,
                    provider_name=provider_class.get_provider_name(),
                    auth_settings=self._settings.providers.fanbox,
                    api_delay=self._settings.downloader.api_delay,
                    api_retries=self._settings.downloader.api_retries,
                )
                # 2. Fanbox用のDownloaderを作成
                downloader = FanboxImageDownloader(
                    api_client=api_client,
                    overwrite=self._settings.downloader.overwrite_existing_images,
                )
                # 3. Fanbox用のFetcherとProcessorを作成
                fetcher = FanboxFetcher(api_client=api_client)
                processor = FanboxContentProcessor(
                    parser=FanboxBlockParser(),
                    mapper=FanboxMetadataMapper(),
                    downloader=downloader,
                    update_checker=TimestampUpdateStrategy(
                        timestamp_key="updatedDatetime"
                    ),
                )

                # 4. Providerに依存を注入して返す
                return provider_class(
                    settings=self._settings,
                    api_client=api_client,
                    downloader=downloader,
                    breaker=self._shared_breaker,
                    repository=self._repository,
                    fetcher=fetcher,
                    processor=processor,
                )

            else:
                # この分岐は provider_class のチェックでカバーされるが念のため
                raise ValueError(
                    f"未定義のプロバイダータイプです: {provider_type.name}"
                )

        except Exception as e:
            # 認証エラーなども含め、依存関係の構築失敗はここで捕捉
            raise RuntimeError(
                f"{provider_type.name} の依存関係の構築に失敗しました: {e}"
            ) from e
