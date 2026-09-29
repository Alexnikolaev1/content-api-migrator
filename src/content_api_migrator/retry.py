"""Retry helpers for transient Merchant API failures."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ApiError) and exc.status in RETRY_STATUSES:
        return True
    return isinstance(exc, RuntimeError) and str(exc).startswith("network error")


def call_with_retries(
    fn: Callable[[], T],
    *,
    retries: int = 3,
    base_delay: float = 0.5,
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except (ApiError, RuntimeError) as exc:
            if not is_retryable(exc) or attempt >= retries:
                raise
            attempt += 1
            sleeper(base_delay * (2 ** (attempt - 1)))
