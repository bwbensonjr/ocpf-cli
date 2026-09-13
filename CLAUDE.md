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
  reports.py        # report endpoints: base-type fan-out, paging, not-found
  commands/race.py  # `ocpf race` — fetch/merge/filter/timeline/render
  commands/filer.py # `ocpf filer` — profile, YTD, recent reports
  commands/expenditures.py  # `ocpf expenditures` — payments made
  commands/reports.py       # `ocpf reports` / `ocpf report` — filings
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
- Free-text filer name-search endpoints are dead (404) **except**
  `reports/log?Name=`, which does a case-insensitive partial match across all
  filers and returns their reports with `cpfId`, `fullNameReverse` and an
  era-correct `officeSought`. Resolution in `resolve.py` is still
  district-first and legislative-only; the log is not wired into it.

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

**`summary` describes the whole filtered set, not the returned page**, so
`withSummary=true` with `PageSize=1` answers a scalar question ("how much did
this filer raise between these dates?") in a single request, with no paging.
`StartDate`/`EndDate` are real parameters — inclusive, `M/D/YYYY`, composable
with `CpfId`, working across year boundaries and back to at least 2010. Verified
for cpfId 14902: `1/1/2024`-`10/31/2024` gives 1,277 receipts / $401,190.59,
where the full calendar year gives 1,646 / $560,090.46.

That gap is the reason `ocpf totals` exists: a year-to-date figure fetched after
a cycle includes post-election money, which follows the outcome. But note the
hazard this creates — because a misnamed filter here is *ignored* rather than
rejected, an ignored date bound returns the filer's entire history (15,411
records for the same filer) looking exactly like a valid, larger answer. Any
summary-only query must verify the bound was applied; `search.fetch_summary`
does this by checking the one record it gets back falls inside the window.

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

### Report endpoints — filed reports and their schedules

A *report* is a filing: the CPF 102 a committee submitted for a reporting
period. This is the data behind the web UI's `Reports/DisplayReport?id=N` page,
and it is the only place special-election money is visible — the depository YTD
feeds carry one cumulative figure per filer per calendar year and are never
segmented by election, so a February-to-March special window does not exist in
them.

- `report/{reportId}` (**singular**; `reports/{id}` is a 404) returns one filing
  in full: header, schedule totals, and the line-item arrays `receipts`,
  `expenditures`, `oopExpenditures`, `inkindContributions`, `liabilities`,
  `subvendorPayments`, plus `isAmendment`/`isAmended`,
  `previousReportId`/`nextReportId` and `ocpfUsReportLink`.
  **It has no 404**: an id below **39** returns HTTP 400, and a well-formed id
  that does not exist returns **HTTP 500** with an empty body. Both mean "no
  such report" — do not report either as an outage.
- `report/pdf/{reportId}` returns the filed PDF (`application/pdf`).
- `reports/baseReportTypes/{cpfId}` lists the categories a filer has filed
  under. A depository committee has up to seven (Principal, Deposit, Year-End
  Summaries, Reimbursement, Subvendor, Other Periodic, Late Contribution); a
  non-depository committee typically has one. `[]` means the filer has filed
  nothing.
- `reports/reportList/{cpfId}` **requires `BaseReportTypeId`** — without it,
  HTTP 400 (`"No base report type ID was provided"`). This is why the endpoint
  notes long listed it as broken; it is not. It takes exactly **one** value: a
  comma-separated `3,8` returns an empty body and a repeated parameter silently
  uses the first, so a complete listing means one call per base report type.
  Returns `{summary: {count, ...}, items: [...]}` with structured `startDate`,
  `endDate`, integer `reportYear`, `startBalance`/`endBalance`, and
  `receiptTotal`/`expenditureTotal` as display strings.
- **`OnlyCurrent` defaults to `true`**, which omits superseded versions of
  amended filings. cpfId 14819, base type 8: 21 by default, 47 with
  `OnlyCurrent=false`. cpfId 14454 across all types: 444 vs 517.
- **`StartIndex` is 1-based and is a record offset, not a page number.** Pages
  start at `1`, `1+PageSize`, `1+2*PageSize`. `StartIndex=0` returns **HTTP 500**
  on `reportList` (on `reports/log` it silently returns `PageSize - 1` records
  instead), and consecutive offsets return overlapping windows. Same trap as
  `search/items`, sharper edges.
- `reports/log` is the other way in: one request, every report type, and the
  **only cross-filer path** in the API (`ReportTypeId`, `Name` and `CpfId`
  filters, all failing *closed* — an unknown `ReportTypeId` returns `[]`). It is
  not used by the commands because its rows are built for a web table:
  `reportingPeriod` arrives in at least three incompatible shapes
  (`7/1/19 - 12/31/19`, `9/1 - 9/30/2026` with no start year, and a bare
  `1/13/26` that is not a range) and `amendmentDisplay` contains literal HTML
  (`<br>Amendment`). It returns the same report set as the `reportList` fan-out
  (517 each for cpfId 14454). Cross-filer work needs it and must parse those
  formats; keep that confined to the log path.

Report types carry both a depository and a non-depository spelling of the same
thing — `Pre-Election Report (Special)` and `Pre-election Report (Special) (ND)`
— so match `reportTypeDescription` as a case-insensitive substring rather than
on the undocumented numeric `reportTypeId`.

All of this lives behind `src/ocpf_cli/reports.py`; go through it rather than
calling `api.get_json("report/...", ...)` directly.

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
