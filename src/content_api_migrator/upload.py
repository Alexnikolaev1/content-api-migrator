"""Upload converted products with retry, resume, delta, concurrency, verify."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from content_api_migrator.auth import access_token
from content_api_migrator.catalog_diff import product_key
from content_api_migrator.client import get_product, insert_product_input
from content_api_migrator.delta import (
    clear_completed,
    load_state,
    mark_success,
    product_hash,
    save_state,
    should_skip,
)
from content_api_migrator.retry import call_with_retries
from content_api_migrator.verify import verify_match

UploadRow = dict[str, Any]
Inserter = Callable[..., dict[str, Any]]
Getter = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class UploadOptions:
    sleep_s: float = 0.05
    limit: int | None = None
    concurrency: int = 1
    retries: int = 3
    delta: bool = False
    verify: bool = False
    state_path: Path | None = None


@dataclass
class UploadCtx:
    account_id: str
    data_source: str
    token: str
    options: UploadOptions
    inserter: Inserter = field(default=insert_product_input)
    getter: Getter = field(default=get_product)
    state: dict[str, Any] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)


def upload_products(
    products: list[dict[str, Any]],
    account_id: str,
    data_source: str,
    options: UploadOptions | None = None,
    **hooks: Any,
) -> dict[str, Any]:
    opts = options or UploadOptions()
    bearer = hooks.get("token")
    bearer = access_token() if bearer is None else bearer
    batch = products if opts.limit is None else products[: opts.limit]
    state = _load_opts_state(opts)
    ctx = UploadCtx(
        account_id,
        data_source,
        bearer,
        opts,
        hooks.get("inserter", insert_product_input),
        hooks.get("getter", get_product),
        state,
    )
    rows = _run_batch(batch, ctx)
    _persist_state(opts, state, rows)
    return _summary(account_id, data_source, batch, rows)


def _load_opts_state(opts: UploadOptions) -> dict[str, Any]:
    if opts.state_path:
        return load_state(opts.state_path)
    return {"completed": {}, "hashes": {}}


def _persist_state(
    opts: UploadOptions, state: dict[str, Any], rows: list[UploadRow]
) -> None:
    if not opts.state_path:
        return
    if all(row["ok"] or row.get("skipped") for row in rows):
        clear_completed(state)
    save_state(opts.state_path, state)


def _run_batch(batch: list[dict[str, Any]], ctx: UploadCtx) -> list[UploadRow]:
    if ctx.options.concurrency <= 1:
        return _run_serial(batch, ctx)
    rows: list[UploadRow | None] = [None] * len(batch)
    workers = ctx.options.concurrency
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_upload_one, i, product, ctx): i
            for i, product in enumerate(batch)
        }
        for future in as_completed(futures):
            rows[futures[future]] = future.result()
    return [row for row in rows if row is not None]


def _run_serial(batch: list[dict[str, Any]], ctx: UploadCtx) -> list[UploadRow]:
    rows: list[UploadRow] = []
    for index, product in enumerate(batch):
        rows.append(_upload_one(index, product, ctx))
        if ctx.options.sleep_s > 0 and index + 1 < len(batch):
            time.sleep(ctx.options.sleep_s)
    return rows


def _upload_one(index: int, product: dict[str, Any], ctx: UploadCtx) -> UploadRow:
    offer_id = str(product.get("offerId", "?"))
    digest = product_hash(product)
    skip = should_skip(product_key(product), digest, ctx.state, ctx.options.delta)
    if skip:
        return _skipped_row(index, offer_id, skip)
    try:
        return _insert_and_maybe_verify(index, product, digest, ctx)
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        return _fail_row(index, offer_id, str(exc))


def _insert_and_maybe_verify(
    index: int, product: dict[str, Any], digest: str, ctx: UploadCtx
) -> UploadRow:
    offer_id = str(product.get("offerId", "?"))

    def do_insert() -> dict[str, Any]:
        return ctx.inserter(ctx.account_id, ctx.data_source, product, ctx.token)

    response = call_with_retries(do_insert, retries=ctx.options.retries)
    name = response.get("name", "")
    if ctx.options.verify:
        _verify_remote(product, ctx)
    with ctx.lock:
        stamped = {**product, "name": name or product.get("name", "")}
        mark_success(ctx.state, stamped, digest)
    return _ok_row(index, offer_id, name)


def _verify_remote(product: dict[str, Any], ctx: UploadCtx) -> None:
    delays = (0.0, 0.4, 0.8)
    last: list[str] = ["verify failed: no attempt"]
    for delay in delays[: ctx.options.retries + 1]:
        if delay:
            time.sleep(delay)

        def do_get() -> dict[str, Any]:
            return ctx.getter(ctx.account_id, product, ctx.token)

        remote = call_with_retries(do_get, retries=ctx.options.retries)
        last = verify_match(product, remote)
        if not last:
            return
    raise RuntimeError("verify failed: " + "; ".join(last))


def _ok_row(index: int, offer_id: str, name: str) -> UploadRow:
    return {
        "index": index,
        "offerId": offer_id,
        "ok": True,
        "skipped": False,
        "name": name,
        "error": "",
    }


def _skipped_row(index: int, offer_id: str, reason: str) -> UploadRow:
    return {
        "index": index,
        "offerId": offer_id,
        "ok": True,
        "skipped": True,
        "name": "",
        "error": reason,
    }


def _fail_row(index: int, offer_id: str, error: str) -> UploadRow:
    return {
        "index": index,
        "offerId": offer_id,
        "ok": False,
        "skipped": False,
        "name": "",
        "error": error,
    }


def _summary(
    account_id: str,
    data_source: str,
    batch: list[dict[str, Any]],
    rows: list[UploadRow],
) -> dict[str, Any]:
    skipped = sum(1 for row in rows if row.get("skipped"))
    ok = sum(1 for row in rows if row["ok"] and not row.get("skipped"))
    failed = sum(1 for row in rows if not row["ok"])
    return {
        "account_id": account_id,
        "data_source": data_source,
        "total": len(batch),
        "ok": ok,
        "skipped": skipped,
        "failed": failed,
        "rows": rows,
    }


def format_upload_report(report: dict[str, Any]) -> str:
    lines = [
        "=== Merchant API upload ===",
        f"account_id: {report['account_id']}",
        f"data_source: {report['data_source']}",
        (
            f"total: {report['total']}  ok: {report['ok']}  "
            f"skipped: {report.get('skipped', 0)}  failed: {report['failed']}"
        ),
    ]
    lines.extend(_format_row(row) for row in report["rows"])
    return "\n".join(lines)


def _format_row(row: UploadRow) -> str:
    if row.get("skipped"):
        return f"  SKIP [{row['index']}] offerId={row['offerId']} ({row['error']})"
    if row["ok"]:
        return f"  OK  [{row['index']}] offerId={row['offerId']} {row['name']}"
    return f"  FAIL [{row['index']}] offerId={row['offerId']}: {row['error']}"
