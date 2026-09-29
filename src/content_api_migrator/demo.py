"""Build audit payload and run offline demo against MockMerchant."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from content_api_migrator.feed import convert_feed
from content_api_migrator.html_report import render_html_report
from content_api_migrator.mock_api import MockMerchant
from content_api_migrator.report import build_dry_run_report
from content_api_migrator.risk import estimate_risk
from content_api_migrator.upload import UploadOptions, upload_products


def build_audit_payload(
    raw_products: list[Any], account_id: str, *, title: str = "Migration audit"
) -> dict[str, Any]:
    dry = build_dry_run_report(raw_products, account_id)
    converted, _errors = convert_feed(raw_products, account_id)
    risk = estimate_risk(converted, dry["failed"], include_unmigrated=True)
    return {
        "title": title,
        "account_id": account_id,
        "total": dry["total"],
        "ok": dry["ok"],
        "failed": dry["failed"],
        "warning_count": dry["warning_count"],
        "errors": dry["errors"],
        "warnings": dry["warnings"],
        "sample_ok": dry["sample_ok"],
        "risk": risk,
        "ready_for_staging": dry["failed"] == 0,
    }


def write_html_report(payload: dict[str, Any], path: Path) -> None:
    path.write_text(render_html_report(payload) + "\n", encoding="utf-8")


def run_demo(
    raw_products: list[Any], account_id: str, html_path: Path
) -> dict[str, Any]:
    payload = build_audit_payload(
        raw_products, account_id, title="Continuity demo audit"
    )
    converted, _errors = convert_feed(raw_products, account_id)
    mock = MockMerchant(account_id)
    upload = upload_products(
        converted,
        account_id,
        f"accounts/{account_id}/dataSources/demo",
        UploadOptions(sleep_s=0, verify=True),
        token="demo",
        inserter=mock.insert,
        getter=mock.get,
    )
    payload["demo_upload"] = {
        "ok": upload["ok"],
        "failed": upload["failed"],
        "skipped": upload.get("skipped", 0),
    }
    write_html_report(payload, html_path)
    return {"payload": payload, "upload": upload, "html_path": str(html_path)}
