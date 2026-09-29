from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from content_api_migrator.auth import access_token
from content_api_migrator.cli import main
from content_api_migrator.client import as_insert_body, insert_product_input, insert_url
from content_api_migrator.upload import (
    UploadOptions,
    format_upload_report,
    upload_products,
)

SAMPLE = {
    "contentLanguage": "en",
    "feedLabel": "US",
    "offerId": "1",
    "productAttributes": {},
}


class _OkResponse:
    def read(self) -> bytes:
        return b'{"name":"accounts/1/productInputs/en~US~1"}'

    def __enter__(self) -> _OkResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_insert_url_and_body_shape():
    url = insert_url("4321", "accounts/4321/dataSources/9")
    assert "productInputs:insert" in url and "dataSource=" in url
    body = as_insert_body({**SAMPLE, "name": "accounts/4321/products/en~US~1"})
    assert "name" not in body and body["offerId"] == "1"


def test_insert_product_input_success():
    result = insert_product_input(
        "1",
        "accounts/1/dataSources/2",
        SAMPLE,
        "tok",
        opener=lambda *_a, **_k: _OkResponse(),
    )
    assert "productInputs" in result["name"]


def test_insert_product_input_http_error():
    payload = b'{"error":{"message":"nope"}}'

    def boom(*_a: object, **_k: object) -> None:
        fp = BytesIO(payload)
        raise HTTPError("https://x", 403, "Forbidden", {}, fp)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="nope"):
        insert_product_input(
            "1", "accounts/1/dataSources/2", SAMPLE, "tok", opener=boom
        )


def test_upload_products_collects_ok_and_fail():
    products = [{**SAMPLE, "offerId": "ok"}, {**SAMPLE, "offerId": "bad"}]

    def fake_insert(
        _account: str, _ds: str, product: dict, _token: str
    ) -> dict[str, str]:
        if product["offerId"] == "bad":
            raise RuntimeError("boom")
        return {"name": "accounts/1/productInputs/en~US~ok"}

    report = upload_products(
        products,
        "1",
        "accounts/1/dataSources/2",
        UploadOptions(sleep_s=0),
        token="x",
        inserter=fake_insert,
    )
    assert report["ok"] == 1 and report["failed"] == 1
    text = format_upload_report(report)
    assert "OK" in text and "FAIL" in text


def test_access_token_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MERCHANT_ACCESS_TOKEN", "env-token")
    assert access_token() == "env-token"


def test_access_token_via_adc(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MERCHANT_ACCESS_TOKEN", raising=False)
    import content_api_migrator.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_adc_token", lambda: "adc-token")
    assert access_token() == "adc-token"


def _write_mini_feed(path: Path) -> None:
    row = {"id": "online:en:US:1", "price": {"value": "1", "currency": "USD"}}
    row["availability"] = "in stock"
    path.write_text(json.dumps([row]), encoding="utf-8")


def test_cli_upload_requires_yes(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    feed = tmp_path / "feed.json"
    _write_mini_feed(feed)
    ds = "accounts/1/dataSources/2"
    code = main(["upload", str(feed), "--account-id", "1", "--data-source", ds])
    assert code == 2
    assert "Re-run with --yes" in capsys.readouterr().err


def _ok_upload_report() -> dict:
    return {
        "account_id": "1",
        "data_source": "ds",
        "total": 1,
        "ok": 1,
        "failed": 0,
        "rows": [{"index": 0, "offerId": "1", "ok": True, "name": "n", "error": ""}],
    }


def test_cli_upload_yes_writes_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    feed, report_path = tmp_path / "feed.json", tmp_path / "up.txt"
    _write_mini_feed(feed)
    monkeypatch.setattr(
        "content_api_migrator.cli.upload_products",
        lambda *_a, **_k: _ok_upload_report(),
    )
    args = [
        "upload",
        str(feed),
        "--account-id",
        "1",
        "--data-source",
        "ds",
        "--yes",
        "--report",
        str(report_path),
    ]
    assert main(args) == 0
    assert "Merchant API upload" in report_path.read_text(encoding="utf-8")


def test_insert_network_error():
    from urllib.error import URLError

    def boom(*_a: object, **_k: object) -> None:
        raise URLError("down")

    with pytest.raises(RuntimeError, match="network error"):
        insert_product_input(
            "1", "accounts/1/dataSources/2", SAMPLE, "tok", opener=boom
        )
