"""Hardening: tests that would fail if price/enum conversion silently regresses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from content_api_migrator import (
    convert_price_to_merchant_api,
    convert_product,
    parse_product,
)
from content_api_migrator.convert import (
    ContentApiPrice,
    InvalidEnumError,
    normalize_availability,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_golden_rejects_floaty_micros_corruption():
    raw = json.loads(
        (FIXTURES / "google_docs_product.json").read_text(encoding="utf-8")
    )
    expected = json.loads(
        (FIXTURES / "google_docs_expected.json").read_text(encoding="utf-8")
    )
    got = convert_product(parse_product(raw), "4321")
    assert got == expected
    # Mutation: if someone used float, 19.99-class values drift — guard the docs case.
    assert got["productAttributes"]["price"]["amountMicros"] == "33450000"
    corrupted = dict(expected)
    bad_attrs = dict(corrupted["productAttributes"])
    bad_attrs["price"] = {"amountMicros": "33449999", "currencyCode": "USD"}
    corrupted["productAttributes"] = bad_attrs
    assert got != corrupted


def test_availability_must_be_merchant_enum_not_uppercased_words():
    assert normalize_availability("in stock") == "IN_STOCK"
    assert normalize_availability("in stock") != "IN STOCK"
    with pytest.raises(InvalidEnumError):
        normalize_availability("totally-unknown-status")


def test_price_never_uses_binary_float_for_1999_cents():
    micros = convert_price_to_merchant_api(ContentApiPrice("19.99", "USD"))
    assert micros["amountMicros"] == "19990000"


def test_price_rounds_half_up_to_micros():
    assert (
        convert_price_to_merchant_api(ContentApiPrice("1.2345675", "USD"))[
            "amountMicros"
        ]
        == "1234568"
    )


def test_missing_availability_is_hard_fail():
    with pytest.raises(KeyError, match="availability"):
        parse_product(
            {
                "id": "online:en:US:1",
                "price": {"value": "1", "currency": "USD"},
            }
        )
