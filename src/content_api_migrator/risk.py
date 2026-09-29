"""Conservative Shopping revenue-at-risk heuristic for client reports."""

from __future__ import annotations

from statistics import mean
from typing import Any

# Honest sales heuristic: ~0.5 order/month per broken/unmigrated SKU.
ORDERS_PER_SKU_MONTH = 0.5
DEFAULT_AVG_PRICE = 25.0


def _price_usd(product: dict[str, Any]) -> float | None:
    attrs = product.get("productAttributes") or {}
    price = attrs.get("price") or {}
    micros = price.get("amountMicros")
    if micros is None:
        return None
    try:
        amount = float(micros) / 1_000_000
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def average_price_usd(products: list[dict[str, Any]]) -> float:
    values = [value for value in (_price_usd(item) for item in products) if value]
    if not values:
        return DEFAULT_AVG_PRICE
    return float(mean(values))


def _usd(skus: int, avg: float) -> float:
    return round(skus * avg * ORDERS_PER_SKU_MONTH, 2)


def estimate_risk(
    converted: list[dict[str, Any]],
    failed_count: int,
    *,
    extra_risk_skus: int = 0,
    include_unmigrated: bool = False,
) -> dict[str, Any]:
    """Estimate monthly revenue at risk from failed rows and/or unmigrated SKUs."""
    avg = average_price_usd(converted)
    failed_skus = failed_count + extra_risk_skus
    unmigrated = len(converted) if include_unmigrated else 0
    return _risk_payload(
        avg, (failed_skus, unmigrated), (_usd(failed_skus, avg), _usd(unmigrated, avg))
    )


def _risk_payload(
    avg: float, counts: tuple[int, int], amounts: tuple[float, float]
) -> dict[str, Any]:
    failed_skus, unmigrated = counts
    failed_usd, unmigrated_usd = amounts
    return {
        "avg_price_usd": round(avg, 2),
        "risk_skus": failed_skus + unmigrated,
        "failed_skus": failed_skus,
        "unmigrated_skus": unmigrated,
        "failed_row_risk_usd": failed_usd,
        "unmigrated_catalog_risk_usd": unmigrated_usd,
        "orders_per_sku_month": ORDERS_PER_SKU_MONTH,
        "estimated_monthly_revenue_at_risk_usd": round(failed_usd + unmigrated_usd, 2),
        "disclaimer": (
            "Heuristic for migration urgency — not a forecast. "
            f"Assumes ~{ORDERS_PER_SKU_MONTH} order/month per SKU."
        ),
    }
