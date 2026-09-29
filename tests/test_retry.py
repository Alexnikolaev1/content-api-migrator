from __future__ import annotations

import pytest

from content_api_migrator.retry import ApiError, call_with_retries, is_retryable


def test_retryable_statuses_and_network():
    assert is_retryable(ApiError("x", status=429))
    assert is_retryable(ApiError("x", status=503))
    assert not is_retryable(ApiError("x", status=400))
    assert is_retryable(RuntimeError("network error: down"))


def test_call_with_retries_succeeds_after_429():
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ApiError("slow down", status=429)
        return "ok"

    sleeps: list[float] = []
    assert call_with_retries(flaky, retries=3, sleeper=sleeps.append) == "ok"
    assert calls["n"] == 3
    assert sleeps == [0.5, 1.0]


def test_call_with_retries_gives_up():
    def always() -> None:
        raise ApiError("nope", status=500)

    with pytest.raises(ApiError) as caught:
        call_with_retries(always, retries=1, sleeper=lambda _d: None)
    assert caught.value.status == 500
