from __future__ import annotations

import json
from pathlib import Path

import pytest

from content_api_migrator import (
    ContentApiPrice,
    ContentApiProduct,
    ContentApiShipping,
    InvalidEnumError,
    InvalidPriceError,
    InvalidProductIdError,
    build_dry_run_report,
    build_merchant_api_product_name,
    convert_feed,
    convert_price_to_merchant_api,
    convert_product,
    normalize_availability,
    normalize_condition,
    parse_content_api_product_id,
    parse_product,
)
from content_api_migrator.cli import main
from content_api_migrator.report import format_dry_run_report

FIXTURES = Path(__file__).parent / "fixtures"


def _sample_product(**overrides: object) -> ContentApiProduct:
    base: dict = {
        "id": "online:en:US:1234",
        "title": "A Tale of Two Cities",
        "description": "A classic novel about the French Revolution",
        "link": "https://example.com/tale-of-two-cities.html",
        "image_link": "https://example.com/tale-of-two-cities.jpg",
        "availability": "in stock",
        "condition": "new",
        "price": ContentApiPrice(value="33.45", currency="USD"),
        "gtins": ("9780007350896",),
        "shipping": (
            ContentApiShipping(
                price=ContentApiPrice("33.45", "USD"),
                country="GB",
                service="1st class post",
            ),
        ),
    }
    base.update(overrides)
    return ContentApiProduct(**base)  # type: ignore[arg-type]


def test_price_matches_google_docs_micros_example():
    price = ContentApiPrice(value="33.45", currency="USD")
    assert convert_price_to_merchant_api(price) == {
        "amountMicros": "33450000",
        "currencyCode": "USD",
    }


def test_price_rejects_invalid_negative_and_empty_currency():
    with pytest.raises(InvalidPriceError):
        convert_price_to_merchant_api(ContentApiPrice("x", "USD"))
    with pytest.raises(InvalidPriceError):
        convert_price_to_merchant_api(ContentApiPrice("-1", "USD"))
    with pytest.raises(InvalidPriceError):
        convert_price_to_merchant_api(ContentApiPrice("1", "  "))


def test_price_avoids_float_rounding():
    result = convert_price_to_merchant_api(ContentApiPrice("19.99", "USD"))
    assert result["amountMicros"] == "19990000"


def test_parse_product_id_and_colons_in_offer_id():
    assert parse_content_api_product_id("online:en:US:1234") == ("en", "US", "1234")
    assert parse_content_api_product_id("online:en:US:sku:x") == ("en", "US", "sku:x")
    with pytest.raises(InvalidProductIdError):
        parse_content_api_product_id("bad")


def test_build_name_and_enums():
    assert build_merchant_api_product_name("4321", "en", "US", "1234") == (
        "accounts/4321/products/en~US~1234"
    )
    slash = build_merchant_api_product_name("4321", "en", "US", "a/b")
    assert slash.startswith("accounts/4321/products/")
    assert "/" not in slash.rsplit("/", 1)[-1]
    assert normalize_availability("in_stock") == "IN_STOCK"
    assert normalize_condition("USED") == "USED"
    with pytest.raises(InvalidEnumError):
        normalize_availability("maybe")


def test_golden_fixture_matches_google_documentation_example():
    raw = json.loads(
        (FIXTURES / "google_docs_product.json").read_text(encoding="utf-8")
    )
    expected = json.loads(
        (FIXTURES / "google_docs_expected.json").read_text(encoding="utf-8")
    )
    assert convert_product(parse_product(raw), "4321") == expected


def test_convert_product_optional_fields_and_empty_lists():
    product = _sample_product(
        gtins=(),
        shipping=(),
        brand="Acme",
        mpn="M-1",
        additional_image_links=("https://example.com/2.jpg",),
        sale_price=ContentApiPrice("29.99", "USD"),
        availability="out of stock",
    )
    attrs = convert_product(product, "1")["productAttributes"]
    assert "gtins" not in attrs
    assert "shipping" not in attrs
    assert attrs["brand"] == "Acme"
    assert attrs["salePrice"]["amountMicros"] == "29990000"
    assert attrs["availability"] == "OUT_OF_STOCK"


def test_parse_accepts_singular_gtin():
    product = parse_product(
        {
            "id": "online:en:US:1",
            "price": {"value": "1", "currency": "USD"},
            "gtin": "123",
            "availability": "in stock",
        }
    )
    assert product.gtins == ("123",)


def test_convert_feed_and_dry_run_report():
    rows = [
        {
            "id": "online:en:US:ok",
            "title": "Ok",
            "link": "https://x",
            "imageLink": "https://y",
            "price": {"value": "1.00", "currency": "USD"},
            "availability": "in stock",
            "gtins": ["1"],
        },
        {"id": "bad", "price": {"value": "x", "currency": "USD"}},
        "nope",
    ]
    converted, errors = convert_feed(rows, "9")
    assert len(converted) == 1 and len(errors) == 2
    report = build_dry_run_report(rows, "9")
    assert report["ok"] == 1 and report["failed"] == 2
    text = format_dry_run_report(report)
    assert "FAIL" in text and "dry-run" in text


def test_cli_convert_and_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    feed = tmp_path / "feed.json"
    feed.write_text(
        json.dumps(
            [
                {
                    "id": "online:en:US:1",
                    "title": "T",
                    "link": "https://a",
                    "imageLink": "https://b",
                    "price": {"value": "2.00", "currency": "USD"},
                    "availability": "in stock",
                    "gtins": ["9"],
                }
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    assert main(["convert", str(feed), "--account-id", "1", "-o", str(out)]) == 0
    assert "amountMicros" in out.read_text(encoding="utf-8")
    assert main(["dry-run", str(feed), "--account-id", "1"]) == 0
    assert "ok: 1" in capsys.readouterr().out


def test_cli_strict_and_bad_input(tmp_path: Path):
    feed = tmp_path / "bad.json"
    feed.write_text('{"no":"array"}', encoding="utf-8")
    assert main(["convert", str(feed), "--account-id", "1"]) == 1
    broken = tmp_path / "rows.json"
    broken.write_text(
        json.dumps(
            [{"id": "online:en:US:1", "price": {"value": "x", "currency": "USD"}}]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    assert (
        main(["convert", str(broken), "--account-id", "1", "-o", str(out), "--strict"])
        == 1
    )
    assert not out.exists()


def test_parse_rejects_local_and_limited_availability():
    with pytest.raises(InvalidProductIdError):
        parse_content_api_product_id("local:en:US:1")
    with pytest.raises(InvalidProductIdError):
        parse_content_api_product_id("online:en::1234")
    with pytest.raises(InvalidEnumError):
        normalize_availability("limited availability")


def test_warning_truncation_in_report():
    rows = [
        {
            "id": f"online:en:US:{i}",
            "price": {"value": "1", "currency": "USD"},
            "availability": "in stock",
        }
        for i in range(25)
    ]
    text = format_dry_run_report(build_dry_run_report(rows, "1"))
    assert "more warnings" in text


def test_cli_writes_report_files(tmp_path: Path):
    feed = tmp_path / "feed.json"
    row = {"id": "online:en:US:1", "price": {"value": "1", "currency": "USD"}}
    row["availability"] = "in stock"
    feed.write_text(json.dumps([row]), encoding="utf-8")
    report, out = tmp_path / "report.txt", tmp_path / "out.json"
    args = [
        "convert",
        str(feed),
        "--account-id",
        "1",
        "-o",
        str(out),
        "--report",
        str(report),
    ]
    assert main(args) == 0
    assert "dry-run" in report.read_text(encoding="utf-8")
    machine = tmp_path / "report.json"
    assert (
        main(["dry-run", str(feed), "--account-id", "1", "--json", str(machine)]) == 0
    )
    assert json.loads(machine.read_text(encoding="utf-8"))["ok"] == 1
