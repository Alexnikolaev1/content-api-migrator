# Delivery audit — Continuity migrator

Prepared for a strict engineer review before client handoff.

## Quality gate

- `.\make.ps1` must exit 0 (format, lint, types, tests, Martin limits, coverage ≥90%).

## Fixes applied in polish pass

| Issue | Resolution |
|---|---|
| `products.get` always base64url | Plain `lang~feed~offerId`; encode only if offerId has `/`, `%`, or `~` |
| Converted `name` vs get URL | `build_merchant_api_product_name` uses same `product_resource_name` encoding |
| Invalid `LIMITED_AVAILABILITY` | Removed; unknown values raise `InvalidEnumError` |
| `$ at risk` = $0 on clean convert | Report includes **unmigrated catalog** risk (sunset exposure) |
| `.env.example` fake vars | Documented CLI flags + real env tokens only |
| Upload partial by default | Convert FAILs abort unless `--allow-partial` |
| `--delta` without `--state` | Hard error |
| Resume ignored digest | Resume only when completed **and** hash matches |
| Delta/resume keyed by offerId only | State key = `contentLanguage~feedLabel~offerId` (multi-locale safe) |
| Catalog list truncation | Raises if `nextPageToken` remains after max pages |
| `local:` channel | Rejected as out of scope |
| Missing `availability` | Hard FAIL (no silent `OUT_OF_STOCK`) |
| Silent field drop | WARN `unsupported fields dropped: …` |
| Verify race | Short backoff retries on mismatch |
| Empty `gtins`/`shipping` | Omitted from payload (not empty arrays) |
| Price micros | `ROUND_HALF_UP` quantize to integer micros |
| Landing JS drift | Aligns channel / availability / micros / gtins with Python; still illustrative |
| `requests` only in optional-dev | Runtime dep (ADC refresh); auth message → `pip install -e .` |
| Diff silent last-wins on dup keys | Reports `duplicate_local` / `duplicate_remote` |
| Risk hero looked like a forecast | Label: heuristic $ at risk (fails + unmigrated) |

## Honest limitations (call out to client)

1. Not every Content API attribute is mapped — unknown keys are warned, not invented.
2. `customBatch`, accounts, shippingsettings, local inventory are out of $990 scope.
3. Live `products.list` diff against a whole Merchant Center can false-positive `missing_in_feed`; prefer `--catalog` scoped export.
4. `--verify` can still fail if Merchant processing is slower than backoff — re-run get later.
5. Landing-page JS converter is **illustrative**; Python CLI is source of truth.
6. Risk $ figures are heuristics for urgency, not forecasts.
7. Pre-polish state files keyed by bare `offerId` are incompatible — delete and re-run once.

## Suggested handoff zip contents

- `src/`, `tests/`, `examples/sample_feed.json`, `docs/`, `landing-page.html`
- `migrate.ps1`, `run.py`, `make.ps1`, `pyproject.toml`, `README.md`, `.env.example`
- Do **not** include: `.coverage`, caches, `demo-report.html`, service-account JSON, private brief `.doc`

## Smoke checklist for the reviewing engineer

1. `.\make.ps1`
2. `.\migrate.ps1 demo -o demo-report.html` → open HTML
3. `.\migrate.ps1 report examples\sample_feed.json --account-id 4321 -o audit-report.html`
4. Confirm golden fixture: `tests/fixtures/google_docs_*.json`
5. Confirm reject: `local:…` id, missing `availability`, `limited availability`
6. Confirm delta: same `offerId` across two locales skips both on second `--delta` run
