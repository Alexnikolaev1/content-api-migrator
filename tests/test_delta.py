from __future__ import annotations

from pathlib import Path

from content_api_migrator.catalog_diff import product_key
from content_api_migrator.delta import (
    load_state,
    mark_success,
    product_hash,
    save_state,
    should_skip,
)
from content_api_migrator.upload import UploadOptions, upload_products

SAMPLE = {
    "contentLanguage": "en",
    "feedLabel": "US",
    "offerId": "1",
    "productAttributes": {"availability": "IN_STOCK", "price": {"amountMicros": "1"}},
}


def test_product_hash_stable_and_sensitive():
    a = product_hash(SAMPLE)
    b = product_hash(dict(SAMPLE))
    assert a == b
    changed = {**SAMPLE, "productAttributes": {"availability": "OUT_OF_STOCK"}}
    assert product_hash(changed) != a


def test_should_skip_resume_and_delta():
    twin = {**SAMPLE, "offerId": "2"}
    digest = product_hash(twin)
    key1 = product_key(SAMPLE)
    key2 = product_key(twin)
    state = {
        "completed": {key1: "name"},
        "hashes": {key1: "x", key2: digest},
    }
    assert should_skip(key1, "x", state, delta=False) == "resume"
    assert should_skip(key2, digest, state, delta=True) == "unchanged"
    assert should_skip("en~US~3", "x", state, delta=True) == ""


def test_resume_requires_matching_hash():
    key = product_key(SAMPLE)
    state = {"completed": {key: "n"}, "hashes": {key: "stale"}}
    assert should_skip(key, "fresh", state, delta=False) == ""
    state["hashes"][key] = "fresh"
    assert should_skip(key, "fresh", state, delta=False) == "resume"


def test_delta_skips_second_upload(tmp_path: Path):
    state_path = tmp_path / "state.json"
    calls = {"n": 0}

    def inserter(*_a: object, **_k: object) -> dict[str, str]:
        calls["n"] += 1
        return {"name": "n"}

    opts = UploadOptions(sleep_s=0, delta=True, state_path=state_path)
    upload_products([SAMPLE], "1", "ds", opts, token="t", inserter=inserter)
    upload_products([SAMPLE], "1", "ds", opts, token="t", inserter=inserter)
    assert calls["n"] == 1
    loaded = load_state(state_path)
    assert product_key(SAMPLE) in loaded["hashes"]


def test_resume_skips_completed(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state: dict[str, dict[str, str]] = {"completed": {}, "hashes": {}}
    mark_success(state, {**SAMPLE, "name": "n"}, product_hash(SAMPLE))
    save_state(state_path, state)
    calls = {"n": 0}

    def inserter(*_a: object, **_k: object) -> dict[str, str]:
        calls["n"] += 1
        return {"name": "n"}

    opts = UploadOptions(sleep_s=0, state_path=state_path)
    report = upload_products([SAMPLE], "1", "ds", opts, token="t", inserter=inserter)
    assert calls["n"] == 0
    assert report["skipped"] == 1


def test_delta_keeps_same_offer_across_locales(tmp_path: Path):
    """Same offerId in en+de must not thrash each other in state."""
    state_path = tmp_path / "state.json"
    en = {**SAMPLE, "contentLanguage": "en", "feedLabel": "US", "offerId": "SKU"}
    de = {**SAMPLE, "contentLanguage": "de", "feedLabel": "DE", "offerId": "SKU"}
    calls = {"n": 0}

    def inserter(*_a: object, **_k: object) -> dict[str, str]:
        calls["n"] += 1
        return {"name": f"n{calls['n']}"}

    opts = UploadOptions(sleep_s=0, delta=True, state_path=state_path)
    first = upload_products([en, de], "1", "ds", opts, token="t", inserter=inserter)
    second = upload_products([en, de], "1", "ds", opts, token="t", inserter=inserter)
    assert first["ok"] == 2
    assert calls["n"] == 2
    assert second["skipped"] == 2
    loaded = load_state(state_path)
    assert product_key(en) in loaded["hashes"]
    assert product_key(de) in loaded["hashes"]
