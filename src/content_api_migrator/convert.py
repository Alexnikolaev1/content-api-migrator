"""Content API for Shopping → Merchant API product conversion.

Field mappings follow Google's migration guides:
https://developers.google.com/merchant/api/guides/compatibility/overview
https://developers.google.com/merchant/api/guides/compatibility/products
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

AVAILABILITY_MAP = {
    "in stock": "IN_STOCK",
    "in_stock": "IN_STOCK",
    "out of stock": "OUT_OF_STOCK",
    "out_of_stock": "OUT_OF_STOCK",
    "preorder": "PREORDER",
    "backorder": "BACKORDER",
}

CONDITION_MAP = {
    "new": "NEW",
    "used": "USED",
    "refurbished": "REFURBISHED",
}


class InvalidPriceError(ValueError):
    pass


class InvalidProductIdError(ValueError):
    pass


class InvalidEnumError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ContentApiPrice:
    value: str
    currency: str


@dataclass(frozen=True, slots=True)
class ContentApiShipping:
    price: ContentApiPrice
    country: str
    service: str


@dataclass(frozen=True, slots=True)
class ContentApiProduct:
    id: str
    title: str
    description: str
    link: str
    image_link: str
    availability: str
    condition: str
    price: ContentApiPrice
    gtins: tuple[str, ...] = field(default_factory=tuple)
    shipping: tuple[ContentApiShipping, ...] = field(default_factory=tuple)
    brand: str = ""
    google_product_category: str = ""
    mpn: str = ""
    additional_image_links: tuple[str, ...] = field(default_factory=tuple)
    sale_price: ContentApiPrice | None = None


def convert_price_to_merchant_api(price: ContentApiPrice) -> dict:
    """Map Content API price to Merchant API micros (Decimal, never float)."""
    try:
        decimal_value = Decimal(price.value)
    except InvalidOperation as exc:
        raise InvalidPriceError(f"'{price.value}' is not a valid decimal.") from exc
    if decimal_value < 0:
        raise InvalidPriceError(f"Price must not be negative: '{price.value}'.")
    if not price.currency.strip():
        raise InvalidPriceError("currency must be a non-empty ISO 4217 code.")
    micros = int(
        (decimal_value * Decimal(1_000_000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return {"amountMicros": str(micros), "currencyCode": price.currency}


def parse_content_api_product_id(product_id: str) -> tuple[str, str, str]:
    """Split channel:lang:feedLabel:offerId (offerId may contain colons)."""
    parts = product_id.split(":", 3)
    if len(parts) != 4 or any(part == "" for part in parts):
        raise InvalidProductIdError(
            f"'{product_id}' must be "
            f"'channel:contentLanguage:feedLabel:offerId' "
            f"({len(parts)} parts found)."
        )
    channel, content_language, feed_label, offer_id = parts
    if channel.lower() != "online":
        raise InvalidProductIdError(
            f"Unsupported channel '{channel}' "
            "(only 'online' product feeds are in scope)."
        )
    return content_language, feed_label, offer_id


def build_merchant_api_product_name(
    account_id: str, content_language: str, feed_label: str, offer_id: str
) -> str:
    from content_api_migrator.client import product_resource_name

    return product_resource_name(
        account_id,
        {
            "contentLanguage": content_language,
            "feedLabel": feed_label,
            "offerId": offer_id,
        },
    )


def normalize_availability(value: str) -> str:
    return _map_enum(value, AVAILABILITY_MAP, "availability")


def normalize_condition(value: str) -> str:
    return _map_enum(value, CONDITION_MAP, "condition")


def _map_enum(value: str, mapping: dict[str, str], field_name: str) -> str:
    key = value.strip().lower()
    if key in mapping:
        return mapping[key]
    already = key.replace(" ", "_").upper()
    if already in mapping.values():
        return already
    raise InvalidEnumError(f"Unknown {field_name} value: '{value}'")


def _shipping_to_merchant(shipping: ContentApiShipping) -> dict:
    return {
        "price": convert_price_to_merchant_api(shipping.price),
        "country": shipping.country,
        "service": shipping.service,
    }


def _optional_attrs(product: ContentApiProduct) -> dict:
    attrs: dict = {}
    if product.brand:
        attrs["brand"] = product.brand
    if product.google_product_category:
        attrs["googleProductCategory"] = product.google_product_category
    if product.mpn:
        attrs["mpn"] = product.mpn
    if product.additional_image_links:
        attrs["additionalImageLinks"] = list(product.additional_image_links)
    if product.sale_price is not None:
        attrs["salePrice"] = convert_price_to_merchant_api(product.sale_price)
    return attrs


def build_product_attributes(product: ContentApiProduct) -> dict:
    attrs = {
        "title": product.title,
        "description": product.description,
        "link": product.link,
        "imageLink": product.image_link,
        "availability": normalize_availability(product.availability),
        "condition": normalize_condition(product.condition),
        "price": convert_price_to_merchant_api(product.price),
    }
    if product.gtins:
        attrs["gtins"] = list(product.gtins)
    if product.shipping:
        attrs["shipping"] = [_shipping_to_merchant(item) for item in product.shipping]
    attrs.update(_optional_attrs(product))
    return attrs


def convert_product(product: ContentApiProduct, account_id: str) -> dict:
    language, feed_label, offer_id = parse_content_api_product_id(product.id)
    name = build_merchant_api_product_name(account_id, language, feed_label, offer_id)
    return {
        "name": name,
        "contentLanguage": language,
        "feedLabel": feed_label,
        "offerId": offer_id,
        "productAttributes": build_product_attributes(product),
    }
