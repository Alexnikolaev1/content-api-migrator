# Continuity — Content API → Merchant API

Tooling to convert Google Content API product feeds to Merchant API format, audit them, and stage-upload with verify.

## Client entrypoints

```powershell
# offline demo for a sales call (mock API + HTML report)
.\migrate.ps1 demo -o demo-report.html

# convert / dry-run / client HTML audit
.\migrate.ps1 convert examples\sample_feed.json --account-id 4321 -o out.json
.\migrate.ps1 dry-run examples\sample_feed.json --account-id 4321
.\migrate.ps1 report examples\sample_feed.json --account-id 4321 -o audit-report.html

# catalog diff (prefer --catalog export for one feed)
.\migrate.ps1 diff examples\sample_feed.json --account-id 4321 --catalog catalog.json
```

Open `landing-page.html` for an **illustrative** in-browser converter. Canonical conversion is always `migrate.ps1 convert`.

## Staging upload

```powershell
$env:MERCHANT_ACCESS_TOKEN = "ya29...."   # or GOOGLE_APPLICATION_CREDENTIALS
.\migrate.ps1 upload feed.json --account-id ID --data-source accounts/ID/dataSources/DS --yes --verify --state .migrate-state.json --delta --concurrency 4 --retries 5
```

- Convert FAILs abort upload unless `--allow-partial`
- `--delta` requires `--state`
- `--verify` retries briefly (Merchant processing lag)
- Auth notes: `.env.example` (flags/env only — no dotenv auto-load)

## Covered fields

`id`, title, description, link, imageLink, availability, condition, price, salePrice, gtin(s), shipping, brand, mpn, googleProductCategory, additionalImageLinks.

Unknown input keys → WARN `unsupported fields dropped`. Only `online:` channel IDs are accepted.
Missing `availability` is a convert FAIL (not defaulted to out of stock).
Delta/resume state keys are `lang~feed~offerId` (safe for multi-locale catalogs).

## Maintainer

```powershell
.\make.ps1   # black, ruff, mypy, pytest≥90%, Martin structure wall
```

Client kit: `docs/client-kit/`. Delivery notes: `docs/DELIVERY.md`. Business plan: `docs/BUSINESS_PLAN.md`.
