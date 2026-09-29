from __future__ import annotations

from content_api_migrator.client import get_product, product_resource_name
from content_api_migrator.upload import UploadOptions, upload_products
from content_api_migrator.verify import verify_match

SAMPLE = {
    "contentLanguage": "en",
    "feedLabel": "US",
    "offerId": "sku1",
    "productAttributes": {
        "availability": "IN_STOCK",
        "price": {"amountMicros": "33450000", "currencyCode": "USD"},
    },
}


def test_verify_match_detects_price_and_availability_bugs():
    remote = {
        "offerId": "sku1",
        "contentLanguage": "en",
        "feedLabel": "US",
        "productAttributes": {
            "availability": "OUT_OF_STOCK",
            "price": {"amountMicros": "1", "currencyCode": "USD"},
        },
    }
    issues = verify_match(SAMPLE, remote)
    assert any("availability" in item for item in issues)
    assert any("amountMicros" in item for item in issues)


def test_verify_match_ok_when_aligned():
    remote = {
        "offerId": "sku1",
        "contentLanguage": "en",
        "feedLabel": "US",
        "productAttributes": SAMPLE["productAttributes"],
    }
    assert verify_match(SAMPLE, remote) == []


def test_product_resource_name_plain_and_encoded():
    plain = product_resource_name("4321", SAMPLE)
    assert plain == "accounts/4321/products/en~US~sku1"
    special = {**SAMPLE, "offerId": "sku/1"}
    encoded = product_resource_name("4321", special)
    assert "/products/" in encoded
    assert "~" not in encoded.split("/products/")[1]


def test_upload_verify_uses_getter():
    def inserter(*_a: object, **_k: object) -> dict[str, str]:
        return {"name": "n"}

    def getter(_account: str, product: dict, _token: str) -> dict:
        return {
            "offerId": product["offerId"],
            "contentLanguage": product["contentLanguage"],
            "feedLabel": product["feedLabel"],
            "productAttributes": product["productAttributes"],
        }

    opts = UploadOptions(sleep_s=0, verify=True)
    report = upload_products(
        [SAMPLE], "1", "ds", opts, token="t", inserter=inserter, getter=getter
    )
    assert report["ok"] == 1 and report["failed"] == 0


def test_get_product_builds_get_request():
    seen: dict[str, str] = {}

    class _Resp:
        def read(self) -> bytes:
            return b'{"offerId":"sku1"}'

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(request: object, timeout: int = 0) -> _Resp:
        del timeout
        seen["url"] = getattr(request, "full_url", "")
        return _Resp()

    result = get_product("1", SAMPLE, "tok", opener=opener)
    assert result["offerId"] == "sku1"
    assert "products/" in seen["url"]


def test_upload_concurrency_and_verify_failure():
    def inserter(*_a: object, **_k: object) -> dict[str, str]:
        return {"name": "n"}

    def bad_getter(_account: str, product: dict, _token: str) -> dict:
        del product
        return {
            "offerId": "nope",
            "contentLanguage": "en",
            "feedLabel": "US",
            "productAttributes": {
                "availability": "OUT_OF_STOCK",
                "price": {"amountMicros": "0", "currencyCode": "USD"},
            },
        }

    products = [{**SAMPLE, "offerId": "a"}, {**SAMPLE, "offerId": "b"}]
    opts = UploadOptions(sleep_s=0, concurrency=2)
    report = upload_products(products, "1", "ds", opts, token="t", inserter=inserter)
    assert report["ok"] == 2
    bad = UploadOptions(sleep_s=0, verify=True)
    failed = upload_products(
        [SAMPLE], "1", "ds", bad, token="t", inserter=inserter, getter=bad_getter
    )
    assert failed["failed"] == 1
