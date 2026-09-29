"""HTTP client for Merchant API productInputs.insert and products.get."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from content_api_migrator.retry import ApiError

BASE = "https://merchantapi.googleapis.com/products/v1"
Opener = Callable[..., Any]


def insert_url(account_id: str, data_source: str) -> str:
    path = f"{BASE}/accounts/{account_id}/productInputs:insert"
    return f"{path}?{urlencode({'dataSource': data_source})}"


def product_id_segment(converted: dict[str, Any]) -> str:
    """Plain lang~feed~offerId, or base64url when offerId has /, %, or ~."""
    lang = converted["contentLanguage"]
    feed = converted["feedLabel"]
    offer = converted["offerId"]
    plain = f"{lang}~{feed}~{offer}"
    if any(char in offer for char in ("/", "%", "~")):
        encoded = base64.urlsafe_b64encode(plain.encode("utf-8")).decode("ascii")
        return encoded.rstrip("=")
    return plain


def product_resource_name(account_id: str, converted: dict[str, Any]) -> str:
    return f"accounts/{account_id}/products/{product_id_segment(converted)}"


def get_product_url(account_id: str, converted: dict[str, Any]) -> str:
    return f"{BASE}/{product_resource_name(account_id, converted)}"


def as_insert_body(converted: dict[str, Any]) -> dict[str, Any]:
    """Drop synthetic name; body matches ProductInput insert."""
    return {
        "contentLanguage": converted["contentLanguage"],
        "feedLabel": converted["feedLabel"],
        "offerId": converted["offerId"],
        "productAttributes": converted["productAttributes"],
    }


def insert_product_input(
    account_id: str,
    data_source: str,
    converted: dict[str, Any],
    token: str,
    *,
    opener: Opener = urlopen,
) -> dict[str, Any]:
    request = _build_insert(account_id, data_source, converted, token)
    return _read_json(request, opener)


def get_product(
    account_id: str,
    converted: dict[str, Any],
    token: str,
    *,
    opener: Opener = urlopen,
) -> dict[str, Any]:
    request = Request(
        get_product_url(account_id, converted),
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    return _read_json(request, opener)


def list_products_page(
    account_id: str,
    token: str,
    *,
    page_size: int = 250,
    page_token: str = "",
    opener: Opener = urlopen,
) -> dict[str, Any]:
    query = {"pageSize": str(page_size)}
    if page_token:
        query["pageToken"] = page_token
    url = f"{BASE}/accounts/{account_id}/products?{urlencode(query)}"
    request = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    return _read_json(request, opener)


def list_all_products(
    account_id: str,
    token: str,
    *,
    page_size: int = 250,
    max_pages: int = 40,
    opener: Opener = urlopen,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    token_page = ""
    for _ in range(max_pages):
        page = list_products_page(
            account_id, token, page_size=page_size, page_token=token_page, opener=opener
        )
        items.extend(page.get("products") or [])
        token_page = page.get("nextPageToken") or ""
        if not token_page:
            return items
    raise RuntimeError(
        f"catalog truncated after {max_pages} pages ({len(items)} products); "
        "pass --catalog export or raise max_pages"
    )


def _build_insert(
    account_id: str, data_source: str, converted: dict[str, Any], token: str
) -> Request:
    return Request(
        insert_url(account_id, data_source),
        data=json.dumps(as_insert_body(converted)).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def _read_json(request: Request, opener: Opener) -> dict[str, Any]:
    try:
        with opener(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raise ApiError(_http_error_message(exc), status=exc.code) from exc
    except URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc


def _http_error_message(exc: HTTPError) -> str:
    raw = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
        message = payload.get("error", {}).get("message")
        if message:
            return f"HTTP {exc.code}: {message}"
    except json.JSONDecodeError:
        pass
    return f"HTTP {exc.code}: {raw or exc.reason}"
