"""CLI gate regressions that an engineer would poke on handoff."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from content_api_migrator.cli import cmd_upload
from content_api_migrator.client import list_all_products
from content_api_migrator.report import collect_warnings


def _ns(**kwargs: object) -> argparse.Namespace:
    defaults = {
        "input": "",
        "account_id": "1",
        "data_source": "accounts/1/dataSources/2",
        "yes": True,
        "allow_partial": False,
        "delta": False,
        "state": None,
        "verify": False,
        "concurrency": 1,
        "retries": 1,
        "limit": None,
        "sleep": 0.0,
        "report": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_upload_refuses_convert_fails_without_allow_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = tmp_path / "feed.json"
    feed.write_text(
        '[{"id":"online:en:US:1","price":{"value":"1","currency":"USD"}}]',
        encoding="utf-8",
    )
    code = cmd_upload(_ns(input=str(feed), yes=True))
    assert code == 1


def test_delta_requires_state(tmp_path: Path) -> None:
    feed = tmp_path / "feed.json"
    feed.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="--delta requires --state"):
        cmd_upload(_ns(input=str(feed), delta=True, state=None, yes=True))


def test_unsupported_fields_warn_text() -> None:
    warnings = collect_warnings(
        {
            "id": "online:en:US:1",
            "title": "t",
            "link": "https://x",
            "imageLink": "https://x/i.jpg",
            "availability": "in stock",
            "condition": "new",
            "gtin": "1",
            "customLabel0": "x",
        },
        0,
    )
    texts = [item["warning"] for item in warnings]
    assert any("unsupported fields dropped: customLabel0" in text for text in texts)


def test_list_truncation_raises() -> None:
    def opener(_req: object, timeout: float = 0) -> object:
        class Resp:
            def __enter__(self) -> Resp:
                return self

            def __exit__(self, *_a: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"products":[{"offerId":"1"}],"nextPageToken":"more"}'

        return Resp()

    with pytest.raises(RuntimeError, match="truncated"):
        list_all_products("1", "t", max_pages=1, opener=opener)
