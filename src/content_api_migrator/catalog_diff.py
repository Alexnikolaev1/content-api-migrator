"""Compare converted feed against live (or exported) Merchant catalog."""

from __future__ import annotations

from typing import Any

from content_api_migrator.verify import actual_checks, expected_checks


def product_key(product: dict[str, Any]) -> str:
    return (
        f"{product.get('contentLanguage')}~{product.get('feedLabel')}~"
        f"{product.get('offerId')}"
    )


def index_by_key(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Last-wins index; see duplicate_keys for collisions."""
    return {product_key(item): item for item in products if product_key(item)}


def duplicate_keys(products: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for item in products:
        key = product_key(item)
        counts[key] = counts.get(key, 0) + 1
    return sorted(key for key, n in counts.items() if n > 1)


def diff_catalog(
    converted: list[dict[str, Any]], remote: list[dict[str, Any]]
) -> dict[str, Any]:
    local = index_by_key(converted)
    live = index_by_key(remote)
    missing_remote = sorted(set(local) - set(live))
    missing_feed = sorted(set(live) - set(local))
    mismatches: list[dict[str, Any]] = []
    for key in sorted(set(local) & set(live)):
        issues = _field_mismatches(local[key], live[key])
        if issues:
            mismatches.append({"key": key, "issues": issues})
    return {
        "local_count": len(local),
        "remote_count": len(live),
        "missing_in_merchant": missing_remote,
        "missing_in_feed": missing_feed,
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
        "duplicate_local": duplicate_keys(converted),
        "duplicate_remote": duplicate_keys(remote),
    }


def _field_mismatches(local: dict[str, Any], remote: dict[str, Any]) -> list[str]:
    expected = expected_checks(local)
    actual = actual_checks(remote)
    return [
        f"{field}: expected {expected[field]!r} got {actual[field]!r}"
        for field in ("availability", "amountMicros", "currencyCode")
        if expected[field] != actual[field]
    ]


def format_diff_report(diff: dict[str, Any]) -> str:
    lines = [
        "=== Merchant catalog diff ===",
        f"local: {diff['local_count']}  remote: {diff['remote_count']}",
        f"missing_in_merchant: {len(diff['missing_in_merchant'])}",
        f"missing_in_feed: {len(diff['missing_in_feed'])}",
        f"mismatches: {diff['mismatch_count']}",
    ]
    lines.extend(_dup_lines("local", diff.get("duplicate_local", [])))
    lines.extend(_dup_lines("remote", diff.get("duplicate_remote", [])))
    for key in diff["missing_in_merchant"][:15]:
        lines.append(f"  + need upload: {key}")
    for key in diff["missing_in_feed"][:10]:
        lines.append(f"  - only in merchant: {key}")
    for item in diff["mismatches"][:15]:
        lines.append(f"  ~ {item['key']}: {'; '.join(item['issues'])}")
    return "\n".join(lines)


def _dup_lines(side: str, keys: list[str]) -> list[str]:
    if not keys:
        return []
    return [f"duplicate_{side}: {len(keys)}"] + [
        f"  ! duplicate {side}: {key}" for key in keys[:10]
    ]
