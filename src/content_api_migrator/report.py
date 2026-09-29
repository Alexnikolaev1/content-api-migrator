"""Dry-run report: counts, failures, and non-fatal quality warnings."""

from __future__ import annotations

from typing import Any

from content_api_migrator.feed import convert_feed

WarningItem = dict[str, Any]

KNOWN_INPUT_KEYS = frozenset(
    {
        "id",
        "title",
        "description",
        "link",
        "imageLink",
        "availability",
        "condition",
        "price",
        "salePrice",
        "gtins",
        "gtin",
        "shipping",
        "brand",
        "googleProductCategory",
        "mpn",
        "additionalImageLinks",
    }
)


def _quality_warnings(
    raw: dict[str, Any], index: int, raw_id: str
) -> list[WarningItem]:
    checks = (
        (not str(raw.get("title", "")).strip(), "empty title"),
        (not str(raw.get("link", "")).strip(), "empty link"),
        (not str(raw.get("imageLink", "")).strip(), "empty imageLink"),
        (not raw.get("gtins") and not raw.get("gtin"), "missing gtin/gtins"),
        ("condition" not in raw, "missing condition (defaulted to new)"),
    )
    return [
        {"index": index, "id": raw_id, "warning": message}
        for bad, message in checks
        if bad
    ]


def collect_warnings(raw: dict[str, Any], index: int) -> list[WarningItem]:
    raw_id = raw.get("id", "?")
    warnings = _quality_warnings(raw, index, str(raw_id))
    unknown = sorted(set(raw) - KNOWN_INPUT_KEYS)
    if unknown:
        warnings.append(
            {
                "index": index,
                "id": raw_id,
                "warning": "unsupported fields dropped: " + ", ".join(unknown),
            }
        )
    return warnings


def build_dry_run_report(raw_products: list[Any], account_id: str) -> dict[str, Any]:
    converted, errors = convert_feed(raw_products, account_id)
    warnings: list[WarningItem] = []
    for index, raw in enumerate(raw_products):
        if isinstance(raw, dict):
            warnings.extend(collect_warnings(raw, index))
    return {
        "account_id": account_id,
        "total": len(raw_products),
        "ok": len(converted),
        "failed": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "sample_ok": converted[:3],
    }


def format_dry_run_report(report: dict[str, Any]) -> str:
    lines = [
        "=== Content API -> Merchant API dry-run ===",
        f"account_id: {report['account_id']}",
        f"total: {report['total']}  ok: {report['ok']}  "
        f"failed: {report['failed']}  warnings: {report['warning_count']}",
    ]
    for item in report["errors"]:
        lines.append(
            f"  FAIL [{item['index']}] id={item['offer_id_or_raw_id']}: {item['error']}"
        )
    for item in report["warnings"][:20]:
        lines.append(f"  WARN [{item['index']}] id={item['id']}: {item['warning']}")
    if report["warning_count"] > 20:
        lines.append(f"  ... {report['warning_count'] - 20} more warnings")
    if report["failed"]:
        lines.append("Do not upload until FAIL rows are fixed.")
    else:
        lines.append("Ready for staging upload (review warnings first).")
    return "\n".join(lines)
