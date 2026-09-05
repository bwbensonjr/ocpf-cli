# CLAUDE.md

Guidance for working in this repository.

## What this is

`ocpf` is a Python CLI (managed with `uv`, built on Typer + httpx) over the
OCPF API at `https://api.ocpf.us/` — a read-only, unauthenticated JSON API.

## Layout

```
src/ocpf_cli/
  cli.py            # Typer app; a callback keeps it in multi-command mode
  api.py            # get_json(path, params) + OcpfApiError + BASE_URL
  render.py         # table rendering, JSON emission, currency formatting
  districts.py      # district name/code -> code resolution
  resolve.py        # filer arg (cpfId or legislative name) -> cpfId
  search.py         # `search/items` client: paging, completeness, shape guards
  commands/race.py  # `ocpf race` — fetch/merge/filter/timeline/render
  commands/filer.py # `ocpf filer` — profile, YTD, recent reports
  commands/expenditures.py  # `ocpf expenditures` — payments made
tests/              # pytest; API and feeds mocked (respx / monkeypatch)
```

## OCPF API reference and data-model facts

The endpoint landscape is mapped in
`../ocpf-analysis/api/ENDPOINT-STATUS.md` (available locally). Key facts that
drove this design:

- The obvious "candidates in a district" endpoints —
  `onballot/candidates/{year}/{code}` and `onballot/finsummaries/...` — are
  **stale** (data stops ~2012) and return empty for current cycles. Do not use
  them for current races.
- The working source of the current legislative field with YTD money is
  `reports/legislative/depository/ytd/{year}`, which returns
  `{ reports: [...], summary: {...} }`. Each report row carries `cpfId`,
  `filerName`, `partyAffiliation`, `districtCodeSought`, `districtCodeHeld`,
  `officeSought`, `receiptsYtd(+Numeric)`, `expendituresYtd(+Numeric)`,
  `currentCashOnHand(+Numeric)`, `startBalance(+Numeric)`, and
  `bankReportEndDate` (format `M/D/YYYY`).
- The non-depository feed is `reports/legislative/race/nd/{year}` and returns a
  **bare list** (not `{reports}`). It is often empty. Merge it with the
  depository feed by `cpfId`, depository winning on conflict.
- `districtCodeHeld == -1` marks a non-incumbent; an incumbent's
  `districtCodeHeld` equals the district code.
- `districts` returns 365 rows of `{office, code, description, ...}`. Filter to
  `office in {"House", "Senate"}` for legislative resolution.
- `filingSchedules/{year}` provides `primaryElectionDate` and
  `generalElectionDate` (timeline context only — money is never split by
  election).
- Free-text filer name-search endpoints are dead (404). Resolution is
  district-first.

### `search/items` — report line items

OCPF publishes a **full OpenAPI spec at `https://api.ocpf.us/swagger/v1/swagger.json`**
covering this endpoint's 29 query parameters. Read it before probing. The
endpoint returns the individual records inside filed reports, and it fails open
in three ways that produce plausible-looking wrong answers rather than errors:

- `SearchTypeCategory` picks the record kind: **`B` expenditures, `R` receipts,
  `S` subvendor payments, `D` donations**. Any *unrecognized* value silently
  returns **receipts** — `E`, `expenditures`, `EXP` and `""` all fall back that
  way, with no error. Never build this parameter from user input.
- `search/recordTypes/{searchTypeCategory}` takes the **same single-letter
  code**, not a word. `search/recordTypes/B` lists the 14 expenditure record
  types (301 General Expenditure, 332 Out-of-pocket candidate expense, ...);
  `R`/`S`/`D` return `[]`. Out-of-pocket types are why an item-search
  expenditure total legitimately exceeds the depository YTD figure.
- **`StartIndex` is 1-based**, not 0-based: `StartIndex=0` and `StartIndex=1`
  both return the first record. Paging from a 0-based offset duplicates the
  record on every page boundary and inflates any total computed from the result.
- A misnamed filter is ignored, not rejected. **`Name` filters the counterparty
  and works; `VendorName` is inert** — passing it returns the entire unfiltered
  database (~1.8M records, $1.55B). An ignored filter is indistinguishable from
  one that matched everything.

Response shape is
`{"summary": {count, total, totalDisplay, description}, "items": [...]}`, with
`summary` null unless `withSummary=true`. Useful parameters: `CpfId`, `Name`,
`StartDate`/`EndDate`, `MinAmount`/`MaxAmount`, `PageSize`, `StartIndex`,
`withSummary`.

Expenditure items carry `vendor`, `purpose`, `clarifiedName`,
`clarifiedPurpose`, `date` (`M/D/YYYY`), `amount` (a **display string** like
`"$1,234.56"`, not a number), `recordTypeDescription`, `reportId`, and
`sourceLink`/`sourceDescription`. `recordTypeDescription` of
`Bank Reported Expenditure` means the payee came off a bank statement and may be
an opaque description (`OUTGOING WIRE TRANSFER`) rather than the true recipient.
`clarifiedName` is OCPF's own resolution of such a payee and should be preferred
when present — it is authoritative, unlike any inference from the raw string.

All of this lives behind `src/ocpf_cli/search.py`; go through it rather than
calling `api.get_json("search/items", ...)` directly.

## Conventions

- Data to stdout; human status/progress and errors to stderr (clig.dev).
- Non-zero exit on failure: bad input, API error, or input that resolves to
  nothing (an unknown district, a name matching no filer). But a user-supplied
  *filter* that narrows a successfully retrieved set to nothing is a finding,
  not a failure — report it on stdout and exit zero (`ocpf expenditures
  <filer> --vendor "..."` with no matching payments).
- All HTTP goes through `api.get_json`; commands raise/catch `OcpfApiError`.
- Double-quoted strings per project style.

## Common commands

```bash
uv sync --extra dev      # install deps + test tooling
uv run pytest            # run tests
uv run ocpf race "..."   # run the CLI from source
```

## Releasing

Notable changes are recorded in [CHANGELOG.md](CHANGELOG.md).

Releases are published to PyPI automatically by GitHub Actions when a version tag
is pushed. Versioning is tag-driven (via `hatch-vcs`), so the tag is the single
source of truth for the package version:

```bash
git tag v0.1.0
git push --tags
```
