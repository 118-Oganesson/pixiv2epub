# FILE: src/pixiv2epub/entrypoints/providers.py
from typing import Dict, Type

from ..infrastructure.providers.base import IProvider
from ..infrastructure.providers.fanbox.provider import FanboxProvider
from ..infrastructure.providers.pixiv.provider import PixivProvider
from ..shared.enums import Provider as ProviderEnum
from ..shared.settings import Settings


class ProviderFactory:
    """
    ProviderEnum に基づいて、対応する具象 Provider クラスのインスタンスを生成します。
    """

    def __init__(self, settings: Settings):
        self._providers: Dict[ProviderEnum, Type[IProvider]] = {
            ProviderEnum.PIXIV: PixivProvider,
            ProviderEnum.FANBOX: FanboxProvider,
        }
        self._settings = settings

    def create(self, provider_type: ProviderEnum) -> IProvider:
        """指定された種類のProviderインスタンスを生成して返します。"""
        provider_class = self._providers.get(provider_type)
        if not provider_class:
            raise ValueError(
                f"サポートされていないプロバイダーです: {provider_type.name}"
            )
        return provider_class(self._settings)
