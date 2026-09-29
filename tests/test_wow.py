from __future__ import annotations

from pathlib import Path

from content_api_migrator.demo import build_audit_payload, run_demo
from content_api_migrator.html_report import render_html_report
from content_api_migrator.risk import estimate_risk


def test_estimate_risk_scales_with_failures():
    products = [
        {
            "productAttributes": {
                "price": {"amountMicros": "10000000", "currencyCode": "USD"}
            }
        }
    ]
    risk = estimate_risk(products, failed_count=4)
    assert risk["avg_price_usd"] == 10.0
    assert risk["estimated_monthly_revenue_at_risk_usd"] == 20.0
    full = estimate_risk(products, failed_count=0, include_unmigrated=True)
    assert full["unmigrated_catalog_risk_usd"] == 5.0


def test_estimate_risk_defaults_when_prices_unusable():
    junk = [
        {"productAttributes": {"price": {"amountMicros": "nope"}}},
        {"productAttributes": {"price": {}}},
        {"productAttributes": {"price": {"amountMicros": "0"}}},
        {"productAttributes": {}},
    ]
    risk = estimate_risk(junk, failed_count=2)
    assert risk["avg_price_usd"] == 25.0
    assert risk["estimated_monthly_revenue_at_risk_usd"] == 25.0


def test_html_report_contains_risk_and_ready(tmp_path: Path):
    row = {
        "id": "online:en:US:1",
        "title": "T",
        "link": "https://a",
        "imageLink": "https://b",
        "price": {"value": "33.45", "currency": "USD"},
        "availability": "in stock",
        "gtins": ["1"],
    }
    payload = build_audit_payload([row], "4321")
    html = render_html_report(payload)
    assert "CONTINUITY" in html and "33450000" in html
    assert "ready_for_staging: YES" in html
    (tmp_path / "a.html").write_text(html, encoding="utf-8")


def test_html_report_truncates_long_lists():
    errors = [{"offer_id_or_raw_id": str(i), "error": "x"} for i in range(15)]
    warnings = [{"id": str(i), "warning": "w"} for i in range(15)]
    risk = {
        "estimated_monthly_revenue_at_risk_usd": 1,
        "disclaimer": "d",
        "avg_price_usd": 1,
        "risk_skus": 1,
        "orders_per_sku_month": 0.5,
    }
    payload = {
        "title": "t",
        "account_id": "1",
        "total": 20,
        "ok": 0,
        "failed": 15,
        "warning_count": 15,
        "errors": errors,
        "warnings": warnings,
        "sample_ok": [],
        "risk": risk,
        "ready_for_staging": False,
    }
    assert "more" in render_html_report(payload)


def test_run_demo_ok(tmp_path: Path):
    row = {
        "id": "online:en:US:1",
        "title": "T",
        "link": "https://a",
        "imageLink": "https://b",
        "price": {"value": "1.00", "currency": "USD"},
        "availability": "in stock",
        "gtins": ["9"],
    }
    path = tmp_path / "demo.html"
    result = run_demo([row], "4321", path)
    assert result["upload"]["ok"] == 1 and "at risk" in path.read_text(encoding="utf-8")
