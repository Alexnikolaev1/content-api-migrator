"""Post-insert verification against products.get."""

from __future__ import annotations

from typing import Any


def expected_checks(converted: dict[str, Any]) -> dict[str, Any]:
    attrs = converted.get("productAttributes", {})
    price = attrs.get("price", {})
    return {
        "offerId": converted.get("offerId"),
        "contentLanguage": converted.get("contentLanguage"),
        "feedLabel": converted.get("feedLabel"),
        "availability": attrs.get("availability"),
        "amountMicros": str(price.get("amountMicros", "")),
        "currencyCode": price.get("currencyCode"),
    }


def actual_checks(remote: dict[str, Any]) -> dict[str, Any]:
    attrs = remote.get("productAttributes", {})
    price = attrs.get("price", {})
    return {
        "offerId": remote.get("offerId"),
        "contentLanguage": remote.get("contentLanguage"),
        "feedLabel": remote.get("feedLabel"),
        "availability": attrs.get("availability"),
        "amountMicros": str(price.get("amountMicros", "")),
        "currencyCode": price.get("currencyCode"),
    }


def verify_match(converted: dict[str, Any], remote: dict[str, Any]) -> list[str]:
    """Return list of mismatch descriptions (empty means verified)."""
    expected = expected_checks(converted)
    actual = actual_checks(remote)
    return [
        f"{key}: expected {expected[key]!r} got {actual[key]!r}"
        for key in expected
        if expected[key] != actual[key]
    ]
