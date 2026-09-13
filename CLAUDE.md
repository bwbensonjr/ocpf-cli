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
  commands/race.py  # `ocpf race` — fetch/merge/filter/timeline/render, plus
                    #   the `--special` roster path (sweep -> stage -> filings)
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
  `onballot/candidates/{year}/{code}` and `onballot/finsummaries/{year}/{code}` —
  **return empty for current cycles**, so do not use them for current races. They
  are not, however, stale past 2012: both carry data through **2018**, and their
  real shape is a two-part gap. Measured on `finsummaries` across Senate codes
  105-145 (`candidates` spot-checked on six of them and matching):
  - **Nothing from 2020 on.** 2020, 2022 and 2024 return zero rows.
  - **Nothing in most odd years.** 2007, 2013, 2015, 2017 and 2019 return zero
    rows across that range; 2011 is the exception and is populated (100 rows).
    2005 was checked on a six-code sample only.

  Populated years are therefore 2004, 2006, 2008, 2010, 2011, 2012, 2014, 2016
  and 2018. This is why `ocpf race`'s historical fallback works for an even year
  and why district resolution tier 3 (which sweeps `finsummaries` for populated
  codes) cannot resolve a renamed district in a pre-2020 **odd** year — the years
  special elections cluster in. See issue #9.
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
  `office in {"House", "Senate"}` for legislative resolution (200 rows: 160
  House, 40 Senate). It is **strictly the present map** and omits retired codes
  entirely — code 140, Senate Worcester & Norfolk through the 2011 cycle,
  appears under no office. There is no year-scoped list: `districts/{year}`
  returns `[]` and `onballot/districts/{year}` is a 404.
- Era-correct district names come from three places instead:
  - The legislative YTD feed pairs an `officeSought` string with a usable
    `districtCodeSought` on every row — `"Senate, Worcester & Norfolk"` with
    code 140 for 2020, and no office string maps to two codes. Feed coverage
    starts abruptly at 2020 (428 rows; 2019 has 13, 2018 has 2, 2017 has 0), so
    this only answers for 2020 and later.
  - `filer/{cpfId}` returns `officeSought` as an object carrying
    `districtCode` **and** `districtDescription`. It reports the filer's **MOST
    RECENT** office sought, not the one they sought in any given year, so it
    surfaces a retired district only for a filer who has sought nothing since —
    cpfId 10315 still reports code 140 / `Worcester & Norfolk` a decade later
    because 10315 stopped running. Do not read it as an era-correct record.
    Across the 2013 Senate 2nd Hampden & Hampshire roster only one filer in four
    still names that seat: Humason (13888) reports Mayoral / Westfield, Bartley
    (12646) House / 5th Hampden, Franco (14025) Governor's Council, and only
    Tautznik (15697) Senate / 2nd Hampden & Hampshire (code 114).
    So a district code is recovered by **tallying a seat's filers and discarding
    every filer whose reported district no longer matches the seat**, never from
    one lookup and never from an unfiltered mode: Brady (14822) and Diehl (14907)
    both filed for Senate 2nd Plymouth & Bristol in 2015 and both now report *2nd
    Plymouth and Norfolk* (169), which an unfiltered tally would return for a
    race in district 128.
    It is reached two ways: by sweeping `onballot/finsummaries/{year}/{code}` for
    populated codes (those rows carry `districtCode: 0` and no district name, so
    the code is known only from the URL and the name only from the filers), which
    answers only for a year `finsummaries` covers; and from the report-log tier
    below, which is seeded by name instead of by code.
  - **The special-election report log** names the seats that held a special in a
    year, from the filings themselves. This is the only source for the pre-2020
    **odd** years, where `finsummaries` has nothing and the legislative feed has
    not started — the years `ocpf race --special` is about. It is seeded from the
    memoized sweep in `reports.py`, so it answers only for seats that held a
    special and costs nothing extra once `--special` has run. Log rows carry no
    district code, so the code is recovered by the filer tally above, for the
    matched seat only — recovering it for every seat in a year costs a request
    per candidate across every special that year (~40 for 2013) to answer about
    one district. A seat whose filers have all moved on resolves with **no code**:
    `District.code` is `int | None`, and `District.full_label` drops the
    `(code N)` rather than printing `code None`. Senate 1st Hampden & Hampshire
    2013 is the live example. Name matching here is **exact only** — this tier
    sees one year's seats, so a substring fallback could resolve `1st Suffolk` to
    `21st Suffolk` with nothing to signal the swap.
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
  not used by the *per-filer* path because its rows are built for a web table:
  `reportingPeriod` arrives in at least three incompatible shapes
  (`7/1/19 - 12/31/19`, `9/1 - 9/30/2026` with no start year, and a bare
  `1/13/26` that is not a range) and `amendmentDisplay` contains literal HTML
  (`<br>Amendment`). It returns the same report set as the `reportList` fan-out
  (517 each for cpfId 14454). Cross-filer work needs it and must parse those
  formats; that parsing is confined to the sweep below.

#### `reports/log` — the cross-filer sweep

`reports/log` is the **only cross-filer path in the API**, and the only way to
answer "which filers sought this seat": `reportList` cannot be queried without a
cpfId, and the on-ballot and legislative feeds carry no special elections at
all. `ocpf race --special` builds its roster here.

- **Its filters fail CLOSED**, unlike `search/items`: an unknown `ReportTypeId`
  (99999) returns `[]` rather than the unfiltered database. A mistyped filter
  here yields an empty answer, not a plausible wrong one.
- **The special-election report types are small and sweepable.** `ReportTypeId=22`
  is pre-primary special (**563 rows**) and `23` is pre-election special (**556**),
  two requests each at `PageSize=500`. Both the depository and non-depository
  spelling of a stage share one id — `Pre-Primary Report (Special)` and
  `Pre-primary Report (Special) (ND)` are both 22 — so one id per stage covers
  both filing regimes.
- **It returns a BARE LIST with no `summary`**, so a short page is the only
  termination signal. `StartIndex` is 1-based here too, but `StartIndex=0`
  silently returns `PageSize - 1` rows instead of erroring.
- **There is no server-side date or district filter.** `StartIndex`, `PageSize`,
  `Name`, `CpfId`, `ReportTypeId` and `ReportTypeCategory` are the whole list, so
  year and district narrowing happen locally over the whole swept type.
- **A log row's money is unsafe.** The log returns *every amendment generation*
  of a filing: cpfId 15658 has four pre-election special rows for
  7/27/2013-8/23/2013, at `$9,940.00` as filed rising to `$13,530.00`. A row's
  total identifies a version, not a candidate — picking the wrong one understates
  that filer by 36%. Money must come from `fetch_reports(cpf_id)`, whose
  `OnlyCurrent=true` default leaves exactly the operative version.
- **Its `reportingPeriod` is a display string** in several shapes, and
  `amendmentDisplay` is literal HTML (`<br>Amendment`). `reports.py` parses the
  period into real dates at the sweep boundary and carries neither the money nor
  the HTML any further; do not retrofit that parsing onto the `reportList` rows,
  which already have structured dates.
- **`CpfId` narrows the log to one filer, and those rows are era-correct.** A
  row's `officeSought` was written when the filing was, which makes
  `reports/log?CpfId=` the era-correct complement to `filer/{cpfId}.officeSought`
  (most-recent-office, above). cpfId 11448 returns 331 rows: 172 reading
  `Senate 1st Plymouth & Bristol` and 159 `Senate 3rd Bristol and Plymouth`. Use
  it to name a district code for a year when the seat's filers have all moved on
  and the filer tally therefore yields nothing — a populated
  `onballot/finsummaries/{year}/{code}` fixes the *code* by construction, so only
  the name is ever missing. This is the second half of the tally rule above: the
  tally answers cheaply when any filer stayed put, the log answers when none did.
  **Its `reportYear` is unreliable** — `None` across all 331 of those rows — so
  the parsed `reportingPeriod` is the only year signal; count a straddling window
  by the year it *ends* in. Behind `reports.offices_sought_in_year`.
- **Differing windows within one stage are one election, not two.** Candidates
  routinely file different windows for the same special — 43 of the 65
  pre-primary district-years carry more than one distinct period, and every one
  collapses to a single election once overlapping windows are merged. Span them;
  do not treat them as rival races.

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
