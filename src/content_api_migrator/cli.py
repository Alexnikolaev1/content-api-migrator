"""CLI: convert, dry-run, upload, report, demo, catalog diff."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from content_api_migrator.auth import access_token
from content_api_migrator.catalog_diff import diff_catalog, format_diff_report
from content_api_migrator.client import list_all_products
from content_api_migrator.demo import build_audit_payload, run_demo, write_html_report
from content_api_migrator.feed import convert_feed
from content_api_migrator.report import build_dry_run_report, format_dry_run_report
from content_api_migrator.upload import (
    UploadOptions,
    format_upload_report,
    upload_products,
)


def _load_feed(path: Path) -> list[Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("feed JSON must be an array of product objects")
    return data


def _write_json(path: Path | None, payload: Any) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if path is None:
        print(text)
    else:
        path.write_text(text + "\n", encoding="utf-8")


def _print_failures(errors: list[dict[str, Any]]) -> None:
    if not errors:
        return
    print(f"{len(errors)} product(s) FAILED:", file=sys.stderr)
    for item in errors:
        print(
            f"  [{item['index']}] id={item['offer_id_or_raw_id']}: {item['error']}",
            file=sys.stderr,
        )


def cmd_convert(args: argparse.Namespace) -> int:
    raw = _load_feed(Path(args.input))
    converted, errors = convert_feed(raw, args.account_id)
    if args.strict and errors:
        print(f"strict: refusing to write ({len(errors)} failures)", file=sys.stderr)
        _print_failures(errors)
        return 1
    _write_json(Path(args.output) if args.output else None, converted)
    if args.report:
        report = build_dry_run_report(raw, args.account_id)
        Path(args.report).write_text(
            format_dry_run_report(report) + "\n", encoding="utf-8"
        )
    _print_failures(errors)
    return 1 if errors else 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    raw = _load_feed(Path(args.input))
    report = build_dry_run_report(raw, args.account_id)
    text = format_dry_run_report(report)
    if args.json:
        _write_json(Path(args.json) if args.json != "-" else None, report)
    print(text, file=sys.stderr if args.json else sys.stdout)
    return 1 if report["failed"] else 0


def _upload_options(args: argparse.Namespace) -> UploadOptions:
    state = Path(args.state) if args.state else None
    return UploadOptions(
        sleep_s=args.sleep,
        limit=args.limit,
        concurrency=args.concurrency,
        retries=args.retries,
        delta=args.delta,
        verify=args.verify,
        state_path=state,
    )


def _refuse_or_plan_upload(
    args: argparse.Namespace, converted: list, errors: list
) -> int:
    if errors and not args.allow_partial:
        print(
            "convert FAILs present; refusing upload "
            "(pass --allow-partial to upload survivors only)",
            file=sys.stderr,
        )
        return 1
    if not args.yes:
        print(
            f"Plan: upload {len(converted)} product(s) to {args.data_source}. "
            "Re-run with --yes to execute.",
            file=sys.stderr,
        )
        return 2
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    if args.delta and not args.state:
        raise ValueError("--delta requires --state so hashes can persist")
    raw = _load_feed(Path(args.input))
    converted, errors = convert_feed(raw, args.account_id)
    _print_failures(errors)
    gate = _refuse_or_plan_upload(args, converted, errors)
    if gate:
        return gate
    report = upload_products(
        converted, args.account_id, args.data_source, _upload_options(args)
    )
    text = format_upload_report(report)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if report["failed"] else 0


def cmd_report(args: argparse.Namespace) -> int:
    raw = _load_feed(Path(args.input))
    payload = build_audit_payload(raw, args.account_id, title=args.title)
    out = Path(args.output)
    write_html_report(payload, out)
    print(f"Wrote HTML report: {out}")
    print(
        "est. monthly $ at risk: "
        f"{payload['risk']['estimated_monthly_revenue_at_risk_usd']}"
    )
    return 1 if payload["failed"] else 0


def cmd_demo(args: argparse.Namespace) -> int:
    feed = Path(args.input) if args.input else Path("examples/sample_feed.json")
    raw = _load_feed(feed)
    html_path = Path(args.output)
    result = run_demo(raw, args.account_id, html_path)
    upload = result["upload"]
    print(f"demo upload ok={upload['ok']} failed={upload['failed']}")
    print(f"HTML report: {html_path}")
    return 1 if upload["failed"] or result["payload"]["failed"] else 0


def cmd_diff(args: argparse.Namespace) -> int:
    raw = _load_feed(Path(args.input))
    converted, errors = convert_feed(raw, args.account_id)
    _print_failures(errors)
    remote = _load_remote_catalog(args)
    diff = diff_catalog(converted, remote)
    text = format_diff_report(diff)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if diff["missing_in_merchant"] or diff["mismatch_count"] else 0


def _load_remote_catalog(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.catalog:
        data = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return list(data.get("products") or [])
        return list(data)
    return list_all_products(args.account_id, access_token())


def _add_convert_parser(sub: Any) -> None:
    convert = sub.add_parser("convert", help="convert feed JSON to Merchant API")
    convert.add_argument("input", help="path to Content API feed JSON array")
    convert.add_argument("--account-id", required=True)
    convert.add_argument("-o", "--output", help="write JSON here (default: stdout)")
    convert.add_argument("--report", help="write human dry-run report path")
    convert.add_argument(
        "--strict", action="store_true", help="no output if any row fails"
    )
    convert.set_defaults(func=cmd_convert)


def _add_dry_run_parser(sub: Any) -> None:
    dry = sub.add_parser("dry-run", help="validate feed without writing products")
    dry.add_argument("input", help="path to Content API feed JSON array")
    dry.add_argument("--account-id", required=True)
    dry.add_argument(
        "--json", nargs="?", const="-", help="machine report path or '-' stdout"
    )
    dry.set_defaults(func=cmd_dry_run)


def _add_upload_flags(up: argparse.ArgumentParser) -> None:
    up.add_argument("--yes", action="store_true", help="actually call the API")
    up.add_argument(
        "--allow-partial",
        action="store_true",
        help="upload survivors even if some rows fail convert",
    )
    up.add_argument("--limit", type=int, default=None, help="upload at most N rows")
    up.add_argument("--sleep", type=float, default=0.05, help="pause between inserts")
    up.add_argument("--concurrency", type=int, default=1, help="parallel inserts")
    up.add_argument("--retries", type=int, default=3, help="retries for 429/5xx")
    up.add_argument(
        "--delta", action="store_true", help="skip unchanged (needs --state)"
    )
    up.add_argument("--verify", action="store_true", help="products.get after insert")
    up.add_argument("--state", help="JSON state file for resume/delta hashes")
    up.add_argument("--report", help="write upload report to this path")


def _add_upload_parser(sub: Any) -> None:
    up = sub.add_parser("upload", help="convert then insert into Merchant API")
    up.add_argument("input", help="path to Content API feed JSON array")
    up.add_argument("--account-id", required=True)
    up.add_argument("--data-source", required=True, help="API data source name")
    _add_upload_flags(up)
    up.set_defaults(func=cmd_upload)


def _add_report_parser(sub: Any) -> None:
    rep = sub.add_parser("report", help="write client HTML audit report")
    rep.add_argument("input", help="path to Content API feed JSON array")
    rep.add_argument("--account-id", required=True)
    rep.add_argument("-o", "--output", default="audit-report.html")
    rep.add_argument("--title", default="Continuity migration audit")
    rep.set_defaults(func=cmd_report)


def _add_demo_parser(sub: Any) -> None:
    demo = sub.add_parser("demo", help="offline demo with mock Merchant API")
    demo.add_argument("input", nargs="?", default="", help="feed JSON (optional)")
    demo.add_argument("--account-id", default="4321")
    demo.add_argument("-o", "--output", default="demo-report.html")
    demo.set_defaults(func=cmd_demo)


def _add_diff_parser(sub: Any) -> None:
    diff = sub.add_parser("diff", help="diff feed vs Merchant catalog")
    diff.add_argument("input", help="path to Content API feed JSON array")
    diff.add_argument("--account-id", required=True)
    diff.add_argument(
        "--catalog",
        help="optional products JSON export; else products.list via OAuth",
    )
    diff.add_argument("--report", help="write text diff report path")
    diff.set_defaults(func=cmd_diff)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content-api-migrator",
        description="Convert Content API feeds and upload to Merchant API.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_convert_parser(sub)
    _add_dry_run_parser(sub)
    _add_upload_parser(sub)
    _add_report_parser(sub)
    _add_demo_parser(sub)
    _add_diff_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
