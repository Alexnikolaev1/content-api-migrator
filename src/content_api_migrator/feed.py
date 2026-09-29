"""Parse Content API JSON rows and convert whole feeds."""

from __future__ import annotations

from typing import Any

from content_api_migrator.convert import (
    ContentApiPrice,
    ContentApiProduct,
    ContentApiShipping,
    convert_product,
)

RowError = dict[str, Any]
FeedResult = tuple[list[dict[str, Any]], list[RowError]]


def _parse_price(data: dict[str, Any]) -> ContentApiPrice:
    return ContentApiPrice(value=str(data["value"]), currency=str(data["currency"]))


def _parse_shipping(items: list[dict[str, Any]]) -> tuple[ContentApiShipping, ...]:
    return tuple(
        ContentApiShipping(
            price=_parse_price(item["price"]),
            country=item["country"],
            service=item["service"],
        )
        for item in items
    )


def _gtins_from(data: dict[str, Any]) -> tuple[str, ...]:
    if "gtins" in data:
        return tuple(str(item) for item in data["gtins"])
    if data.get("gtin"):
        return (str(data["gtin"]),)
    return ()


def parse_product(data: dict[str, Any]) -> ContentApiProduct:
    sale = data.get("salePrice")
    if "availability" not in data or not str(data["availability"]).strip():
        raise KeyError("availability")
    return ContentApiProduct(
        id=data["id"],
        title=data.get("title", ""),
        description=data.get("description", ""),
        link=data.get("link", ""),
        image_link=data.get("imageLink", ""),
        availability=str(data["availability"]),
        condition=str(data.get("condition", "new")),
        price=_parse_price(data["price"]),
        gtins=_gtins_from(data),
        shipping=_parse_shipping(data.get("shipping", [])),
        brand=data.get("brand", ""),
        google_product_category=data.get("googleProductCategory", ""),
        mpn=data.get("mpn", ""),
        additional_image_links=tuple(data.get("additionalImageLinks", [])),
        sale_price=_parse_price(sale) if sale else None,
    )


def convert_feed(raw_products: list[Any], account_id: str) -> FeedResult:
    converted: list[dict[str, Any]] = []
    errors: list[RowError] = []
    for index, raw in enumerate(raw_products):
        try:
            if not isinstance(raw, dict):
                raise TypeError("product row must be a JSON object")
            converted.append(convert_product(parse_product(raw), account_id))
        except (KeyError, TypeError, ValueError) as exc:
            raw_id = raw.get("id", "?") if isinstance(raw, dict) else "?"
            errors.append(
                {"index": index, "offer_id_or_raw_id": raw_id, "error": str(exc)}
            )
    return converted, errors
