"""Client-facing HTML audit report (self-contained single file)."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _row_pair(before: str, after: str) -> str:
    return (
        f"<tr><td class='from'>{_esc(before)}</td>"
        f"<td class='to'>{_esc(after)}</td></tr>"
    )


def _sample_rows(samples: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in samples[:5]:
        rows.extend(_one_sample(item))
    return "\n".join(rows)


def _one_sample(item: dict[str, Any]) -> list[str]:
    attrs = item.get("productAttributes", {})
    price = attrs.get("price", {})
    before_id = (
        f"online:{item.get('contentLanguage')}:{item.get('feedLabel')}:"
        f"{item.get('offerId')}"
    )
    after_id = (
        f"{item.get('contentLanguage')}~{item.get('feedLabel')}~{item.get('offerId')}"
    )
    micros = f"{price.get('amountMicros')} {price.get('currencyCode')}"
    return [
        _row_pair(before_id, after_id),
        _row_pair("price → micros", micros),
        _row_pair("availability", str(attrs.get("availability", ""))),
    ]


def _fail_items(items: list[dict[str, Any]], limit: int = 12) -> str:
    lines = []
    for item in items[:limit]:
        oid = item.get("offer_id_or_raw_id", "?")
        lines.append(f"<li>{_esc(oid)}: {_esc(item.get('error', ''))}</li>")
    if len(items) > limit:
        lines.append(f"<li>… {len(items) - limit} more</li>")
    return "\n".join(lines) if lines else "<li>none</li>"


def _warn_items(items: list[dict[str, Any]], limit: int = 12) -> str:
    lines = []
    for item in items[:limit]:
        lines.append(
            f"<li>{_esc(item.get('id', '?'))}: {_esc(item.get('warning', ''))}</li>"
        )
    if len(items) > limit:
        lines.append(f"<li>… {len(items) - limit} more</li>")
    return "\n".join(lines) if lines else "<li>none</li>"


def _context(payload: dict[str, Any]) -> dict[str, str]:
    risk = payload.get("risk", {})
    ready = "YES" if payload.get("ready_for_staging") else "NO"
    return {
        "title": _esc(payload.get("title", "Continuity migration audit")),
        "account": _esc(payload.get("account_id", "?")),
        "ready": ready,
        "total": _esc(payload.get("total", 0)),
        "ok": _esc(payload.get("ok", 0)),
        "failed": _esc(payload.get("failed", 0)),
        "warnings": _esc(payload.get("warning_count", 0)),
        "risk_usd": _esc(risk.get("estimated_monthly_revenue_at_risk_usd", 0)),
        "sample_rows": _sample_rows(payload.get("sample_ok", [])),
        "fail_list": _fail_items(payload.get("errors", [])),
        "warn_list": _warn_items(payload.get("warnings", [])),
        "disclaimer": _esc(risk.get("disclaimer", "")),
        "avg_price": _esc(risk.get("avg_price_usd", 0)),
        "risk_skus": _esc(risk.get("risk_skus", 0)),
        "orders": _esc(risk.get("orders_per_sku_month", 0)),
    }


def render_html_report(payload: dict[str, Any]) -> str:
    template = (
        Path(__file__).with_name("report_template.html").read_text(encoding="utf-8")
    )
    return template.format(**_context(payload))
