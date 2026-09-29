"""In-memory Merchant API stand-in for demos (no Google credentials)."""

from __future__ import annotations

from typing import Any

from content_api_migrator.client import as_insert_body, product_resource_name


class MockMerchant:
    """Stores inserts and serves get/list like a tiny Merchant Center."""

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        self.products: dict[str, dict[str, Any]] = {}

    def insert(
        self, _account: str, _data_source: str, converted: dict[str, Any], _token: str
    ) -> dict[str, Any]:
        body = as_insert_body(converted)
        key = f"{body['contentLanguage']}~{body['feedLabel']}~{body['offerId']}"
        product_name = converted.get("name") or product_resource_name(
            self.account_id, converted
        )
        remote = {
            "name": product_name,
            "offerId": body["offerId"],
            "contentLanguage": body["contentLanguage"],
            "feedLabel": body["feedLabel"],
            "productAttributes": body["productAttributes"],
        }
        self.products[key] = remote
        return {"name": product_name.replace("/products/", "/productInputs/"), **body}

    def get(
        self, _account: str, converted: dict[str, Any], _token: str
    ) -> dict[str, Any]:
        key = (
            f"{converted['contentLanguage']}~{converted['feedLabel']}~"
            f"{converted['offerId']}"
        )
        if key not in self.products:
            raise RuntimeError(f"mock: product not found: {key}")
        return self.products[key]

    def list_all(self) -> list[dict[str, Any]]:
        return list(self.products.values())
