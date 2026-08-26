"""WebIQ 客户端，供网页搜索与图片搜索共用。"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from . import config

logger = logging.getLogger(__name__)

_client = None
_lock = threading.Lock()


def client():
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client
        from webiq import ApiKeyAuth, WebIQClient

        _client = WebIQClient(auth=ApiKeyAuth(api_key=config.require("WEBIQ_API_KEY")))
        return _client


def _retryable(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(k in message for k in ("rate limit", "429", "timeout", "temporarily"))


def search_with_retry(
    search_func: Callable[..., Any], query: str, max_results: int, attempts: int = 3
):
    """WebIQ 偶发限流，做小幅指数退避。"""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return search_func(query=query, max_results=max_results)
        except Exception as exc:
            last_error = exc
            if attempt == attempts or not _retryable(exc):
                raise
            time.sleep(0.8 * attempt)
    raise last_error  # type: ignore[misc]
