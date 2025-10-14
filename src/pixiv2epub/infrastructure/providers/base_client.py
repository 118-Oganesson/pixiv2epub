# FILE: src/pixiv2epub/infrastructure/providers/base_client.py
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Type

from loguru import logger
from requests.exceptions import RequestException

from ...shared.exceptions import ApiError, AuthenticationError


class BaseApiClient(ABC):
    """APIクライアントの共通ロジック（リトライ、エラーハンドリング）を実装する基底クラス。"""

    def __init__(self, api_delay: float = 1.0, api_retries: int = 3):
        self.delay = api_delay
        self.retries = api_retries

    @property
    @abstractmethod
    def _api_exception_class(self) -> Type[Exception]:
        """具象クライアントが捕捉すべきメインの例外クラスを返します。"""
        raise NotImplementedError

    def _safe_api_call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """API呼び出しをリトライ機構付きで安全に実行します。"""
        last_exception = None
        for attempt in range(1, self.retries + 1):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.delay)
                return result
            except (self._api_exception_class, RequestException) as e:
                last_exception = e
                status_code = getattr(getattr(e, "response", None), "status_code", None)

                # 認証エラー
                if status_code in [401, 403]:
                    raise AuthenticationError(
                        f"API認証エラー (HTTP {status_code})", provider_name=None
                    ) from e

                # 回復不能なクライアントエラー
                if status_code and 400 <= status_code < 500:
                    logger.error(
                        f"API '{func.__name__}' で回復不能なクライアントエラー (HTTP {status_code})"
                    )
                    raise ApiError(
                        f"APIクライアントエラー (HTTP {status_code})",
                        provider_name=None,
                    ) from e

                logger.warning(
                    f"API '{func.__name__}' 呼び出し中にエラー (試行 {attempt}/{self.retries}): {e} (HTTP: {status_code or 'N/A'})"
                )
                if attempt == self.retries:
                    break
                time.sleep(self.delay * attempt)

        logger.error(f"API呼び出しが最終的に失敗しました: {func.__name__}")
        raise ApiError(
            f"API呼び出しがリトライ上限に達しました: {func.__name__}",
            provider_name=None,
        ) from last_exception
