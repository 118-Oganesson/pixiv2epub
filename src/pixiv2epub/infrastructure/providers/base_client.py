# FILE: src/pixiv2epub/infrastructure/providers/base_client.py
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Type

from loguru import logger
from pybreaker import CircuitBreaker, CircuitBreakerError
from requests.exceptions import RequestException

from ...shared.exceptions import ApiError, AuthenticationError


class BaseApiClient(ABC):
    """APIクライアントの共通ロジック（リトライ、エラーハンドリング）を実装する基底クラス。"""

    def __init__(
        self, breaker: CircuitBreaker, api_delay: float = 1.0, api_retries: int = 3
    ):
        self.breaker = breaker
        self.delay = api_delay
        self.retries = api_retries

    @property
    @abstractmethod
    def _api_exception_class(self) -> Type[Exception]:
        """具象クライアントが捕捉すべきメインの例外クラスを返します。"""
        raise NotImplementedError

    def _execute_with_retries(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """API呼び出しをリトライ機構付きで実行します。"""
        last_exception = None
        for attempt in range(1, self.retries + 1):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.delay)
                return result
            except (self._api_exception_class, RequestException) as e:
                last_exception = e
                status_code = getattr(getattr(e, "response", None), "status_code", None)

                if status_code in [401, 403]:
                    raise AuthenticationError(
                        f"API認証エラー (HTTP {status_code})", provider_name=None
                    ) from e

                if status_code and 400 <= status_code < 500:
                    logger.error(
                        "API '{}' で回復不能なクライアントエラー (HTTP {})",
                        func.__name__,
                        status_code,
                    )
                    raise ApiError(
                        f"APIクライアントエラー (HTTP {status_code})",
                        provider_name=None,
                    ) from e

                logger.warning(
                    "API '{}' 呼び出し中にエラー (試行 {}/{}): {} (HTTP: {})",
                    func.__name__,
                    attempt,
                    self.retries,
                    e,
                    status_code or "N/A",
                )
                if attempt < self.retries:
                    time.sleep(self.delay * (attempt + 1))  # Backoff delay

        logger.error("API呼び出しが最終的に失敗しました: {}", func.__name__)
        raise ApiError(
            f"API呼び出しがリトライ上限に達しました: {func.__name__}",
            provider_name=None,
        ) from last_exception

    def _safe_api_call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        API呼び出しをサーキットブレーカーとリトライ機構付きで安全に実行します。
        サーキットが開いている場合、この関数は即座に失敗します。
        """
        try:
            return self.breaker.call(self._execute_with_retries, func, *args, **kwargs)
        except CircuitBreakerError as e:
            logger.error(
                "サーキットブレーカー作動中。API '{}' の呼び出しを中止しました。",
                func.__name__,
            )
            raise ApiError(
                "サービスが一時的に利用不可のようです。しばらくしてから再試行してください (サーキットブレーカー作動中)。"
            ) from e
