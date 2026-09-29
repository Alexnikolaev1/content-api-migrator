from __future__ import annotations

import json
from pathlib import Path

from content_api_migrator.catalog_diff import diff_catalog, format_diff_report
from content_api_migrator.cli import main
from content_api_migrator.client import list_all_products

LOCAL = {
    "contentLanguage": "en",
    "feedLabel": "US",
    "offerId": "1",
    "productAttributes": {
        "availability": "IN_STOCK",
        "price": {"amountMicros": "1000000", "currencyCode": "USD"},
    },
}


def test_diff_finds_missing_and_mismatch():
    remote_bad = {
        **LOCAL,
        "offerId": "2",
        "productAttributes": {
            "availability": "OUT_OF_STOCK",
            "price": {"amountMicros": "1", "currencyCode": "USD"},
        },
    }
    local = [LOCAL, {**LOCAL, "offerId": "2"}]
    diff = diff_catalog(local, [LOCAL, remote_bad])
    assert diff["mismatch_count"] == 1
    only_local = diff_catalog([LOCAL], [])
    assert only_local["missing_in_merchant"] == ["en~US~1"]
    assert "need upload" in format_diff_report(only_local)


def test_diff_reports_duplicate_keys():
    twin = [LOCAL, {**LOCAL, "productAttributes": dict(LOCAL["productAttributes"])}]
    diff = diff_catalog(twin, [])
    assert diff["duplicate_local"] == ["en~US~1"]
    assert "duplicate local: en~US~1" in format_diff_report(diff)


class _Resp:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_list_products_pagination():
    pages = [
        {"products": [{"offerId": "a"}], "nextPageToken": "n1"},
        {"products": [{"offerId": "b"}], "nextPageToken": ""},
    ]
    state = {"i": 0}

    def opener(request: object, timeout: int = 0) -> _Resp:
        del request, timeout
        idx = min(state["i"], len(pages) - 1)
        state["i"] += 1
        return _Resp(pages[idx])

    items = list_all_products("1", "tok", opener=opener)
    assert [item["offerId"] for item in items] == ["a", "b"]


def _mini_feed(path: Path) -> None:
    row = {
        "id": "online:en:US:1",
        "title": "T",
        "link": "https://a",
        "imageLink": "https://b",
        "price": {"value": "2.00", "currency": "USD"},
        "availability": "in stock",
        "gtins": ["1"],
    }
    path.write_text(json.dumps([row]), encoding="utf-8")


def test_cli_report_and_diff(tmp_path: Path):
    feed, html = tmp_path / "feed.json", tmp_path / "r.html"
    _mini_feed(feed)
    assert main(["report", str(feed), "--account-id", "1", "-o", str(html)]) == 0
    assert "CONTINUITY" in html.read_text(encoding="utf-8")
    catalog = tmp_path / "cat.json"
    catalog.write_text(json.dumps({"products": []}), encoding="utf-8")
    code = main(["diff", str(feed), "--account-id", "1", "--catalog", str(catalog)])
    assert code == 1


def test_cli_demo(tmp_path: Path):
    feed = tmp_path / "feed.json"
    _mini_feed(feed)
    out = tmp_path / "demo.html"
    assert main(["demo", str(feed), "--account-id", "1", "-o", str(out)]) == 0
    assert out.exists()
