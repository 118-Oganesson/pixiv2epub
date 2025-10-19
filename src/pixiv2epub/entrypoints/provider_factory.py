# FILE: src/pixiv2epub/entrypoints/provider_factory.py

from typing import Callable, Dict

from pybreaker import CircuitBreaker

from ..domain.interfaces import IProvider, IWorkspaceRepository
from ..infrastructure.providers.fanbox.client import FanboxApiClient
from ..infrastructure.providers.fanbox.content_processor import FanboxContentProcessor
from ..infrastructure.providers.fanbox.downloader import FanboxImageDownloader
from ..infrastructure.providers.fanbox.fetcher import FanboxFetcher
from ..infrastructure.providers.fanbox.provider import FanboxProvider
from ..infrastructure.providers.pixiv.client import PixivApiClient
from ..infrastructure.providers.pixiv.content_processor import PixivContentProcessor
from ..infrastructure.providers.pixiv.downloader import (
    ImageDownloader as PixivImageDownloader,
)
from ..infrastructure.providers.pixiv.fetcher import PixivFetcher
from ..infrastructure.providers.pixiv.provider import PixivProvider
from ..infrastructure.repositories.filesystem import FileSystemWorkspaceRepository
from ..infrastructure.strategies.mappers import (
    FanboxMetadataMapper,
    PixivMetadataMapper,
)
from ..infrastructure.strategies.parsers import FanboxBlockParser, PixivTagParser
from ..infrastructure.strategies.update_checkers import (
    ContentHashUpdateStrategy,
    TimestampUpdateStrategy,
)
from ..shared.enums import Provider as ProviderEnum
from ..shared.settings import Settings


class ProviderFactory:
    """
    ProviderEnum に基づいて、対応する具象 Provider クラスのインスタンスを生成します。
    依存関係の注入は、プロバイダーごとに用意されたビルダーメソッドが担当します。
    """

    def __init__(self, settings: Settings):
        self._settings = settings

        # ファクトリで共有リソースを一度だけ作成する
        self._shared_breaker = CircuitBreaker(
            fail_max=self._settings.downloader.circuit_breaker.fail_max,
            reset_timeout=self._settings.downloader.circuit_breaker.reset_timeout,
        )
        self._repository: IWorkspaceRepository = FileSystemWorkspaceRepository(
            self._settings.workspace
        )

        # プロバイダー種別と、そのプロバイダーを構築するメソッドを紐付けるレジストリ
        self._builders: Dict[ProviderEnum, Callable[[], IProvider]] = {
            ProviderEnum.PIXIV: self._build_pixiv_provider,
            ProviderEnum.FANBOX: self._build_fanbox_provider,
        }

    def _build_pixiv_provider(self) -> IProvider:
        """PixivProviderとその依存関係を構築します。"""
        provider_name = PixivProvider.get_provider_name()

        # 1. 依存オブジェクトの作成
        api_client = PixivApiClient(
            breaker=self._shared_breaker,
            provider_name=provider_name,
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
        return PixivProvider(
            settings=self._settings,
            api_client=api_client,
            breaker=self._shared_breaker,
            fetcher=fetcher,
            processor=processor,
            repository=self._repository,
        )

    def _build_fanbox_provider(self) -> IProvider:
        """FanboxProviderとその依存関係を構築します。"""
        provider_name = FanboxProvider.get_provider_name()

        # 1. Fanbox用のApiClientを作成
        api_client = FanboxApiClient(
            breaker=self._shared_breaker,
            provider_name=provider_name,
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
            update_checker=TimestampUpdateStrategy(timestamp_key="updatedDatetime"),
        )

        # 4. Providerに依存を注入して返す
        return FanboxProvider(
            settings=self._settings,
            api_client=api_client,
            breaker=self._shared_breaker,
            repository=self._repository,
            fetcher=fetcher,
            processor=processor,
        )

    def create(self, provider_type: ProviderEnum) -> IProvider:
        """
        指定された種類のProviderインスタンスを生成して返します。
        巨大なif/elifブロックの代わりに、ビルダーの辞書を使います。
        """
        builder = self._builders.get(provider_type)
        if not builder:
            raise ValueError(
                f"サポートされていないプロバイダーです: {provider_type.name}"
            )

        try:
            return builder()
        except Exception as e:
            # 認証エラーなども含め、依存関係の構築失敗はここで捕捉
            raise RuntimeError(
                f"{provider_type.name} の依存関係の構築に失敗しました: {e}"
            ) from e
