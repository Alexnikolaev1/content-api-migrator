"""Delta uploads: stable hashes and on-disk state for resume/skip."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from content_api_migrator.catalog_diff import product_key


def product_hash(product: dict[str, Any]) -> str:
    """Hash insert-relevant fields so unchanged SKUs can be skipped."""
    payload = {
        "contentLanguage": product.get("contentLanguage"),
        "feedLabel": product.get("feedLabel"),
        "offerId": product.get("offerId"),
        "productAttributes": product.get("productAttributes"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"completed": {}, "hashes": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "completed": dict(data.get("completed", {})),
        "hashes": dict(data.get("hashes", {})),
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def should_skip(key: str, digest: str, state: dict[str, Any], delta: bool) -> str:
    """Return skip reason or empty string when upload should proceed.

    ``key`` is ``contentLanguage~feedLabel~offerId`` (see product_key).
    """
    hashes = state.get("hashes", {})
    completed = state.get("completed", {})
    if key in completed and hashes.get(key) == digest:
        return "resume"
    if delta and hashes.get(key) == digest:
        return "unchanged"
    return ""


def mark_success(state: dict[str, Any], product: dict[str, Any], digest: str) -> None:
    key = product_key(product)
    name = product.get("name", "")
    state.setdefault("completed", {})[key] = name
    state.setdefault("hashes", {})[key] = digest


def clear_completed(state: dict[str, Any]) -> None:
    """Keep hashes for delta; clear resume markers after a full successful run."""
    state["completed"] = {}
