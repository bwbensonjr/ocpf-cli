## Why

Every `ocpf` command so far answers a question about *aggregates*: `race` gives
the field and its year-to-date money, `filer` gives one committee's profile and
totals, `expenditures` gives its payments as a flat stream of line items. None of
them can show you **a filing** — the CPF 102 a candidate actually submitted, with
its reporting period, its start and end balance, and its schedules.

That gap is most visible in exactly the case where the existing commands go
blind: a **special election**. The depository year-to-date feeds behind
`ocpf race` carry one cumulative number per filer per calendar year and are not
segmented by election, so a February-to-March special-election window is
invisible in them. The filing that covers that window — `Pre-election Report
(Special)` — exists, is public, and is served by the API, but today the only way
to read it is to open the OCPF web UI at
`https://www.ocpf.us/reports/displayreport?id=170378`. The CLI has no path to it
at all: it never calls a `report/*` endpoint.

The endpoints are healthy and better than the project's notes suggest. A session
verified the whole chain against that exact report, and turned up two facts that
correct the repo's current API reference: `reports/reportList/{cpfId}` is not
broken, it simply *requires* `BaseReportTypeId`; and free-text filer name search
is **not** entirely dead — `reports/log?Name=` works.

## What Changes

- Add the command
  `ocpf reports <filer> [--year <year>] [--type <text>] [--since <date>] [--until <date>] [--limit <n>] [--json]`,
  which lists the reports a committee has filed — one row per filing with report
  id, report type, reporting period, date filed, amendment marker, and the
  receipt and expenditure totals for that period. This is the index a user needs
  to find a pre-election, pre-primary, post-election, or special-election filing
  and learn its report id.
- Add the command
  `ocpf report <report-id> [--schedule <name>...] [--json]`, which renders a
  single filing: its header (committee, candidate, office and district sought,
  treasurer, bank, reporting period, date filed, amendment lineage), its
  schedule totals (start balance, itemized and unitemized receipts and
  expenditures, in-kind, liabilities, end balance), and — on request — the line
  items of a named schedule. This is the CLI equivalent of the web UI's
  DisplayReport page.
- Back the listing with **`reports/baseReportTypes/{cpfId}` followed by one
  `reports/reportList/{cpfId}` call per base report type**. The alternative,
  `reports/log?CpfId=...`, is a single request and returns the same reports, but
  its rows are display strings: `reportingPeriod` arrives in at least three
  incompatible shapes (`7/1/19 - 12/31/19`, `9/1 - 9/30/2026`, and a bare
  `1/13/26`), and `amendmentDisplay` contains literal HTML (`<br>Amendment`).
  `reportList` returns the same filings with structured `startDate`, `endDate`,
  and integer `reportYear`, plus per-filing `startBalance`/`endBalance` and
  boolean `isAmendment`/`isAmended` with `previousReportId`. The fan-out is
  bounded — seven base report types for a twenty-year depository committee — and
  the two sources agree exactly: for cpfId 14454 both return 517 reports.
- Default the listing to **current filings only**, with a flag to include
  superseded ones. `reportList` defaults to `OnlyCurrent=true`; passing
  `OnlyCurrent=false` adds the superseded versions of amended filings (for cpfId
  14819: 21 current, 47 including superseded). A listing that silently shows a
  filing three times because it was amended twice is worse than one that shows
  the operative version and says so.
- Back the detail view with **`report/{reportId}`**, which returns the full
  filing including `receipts`, `expenditures`, `oopExpenditures`,
  `inkindContributions`, `liabilities`, and `subvendorPayments`.
- Page correctly. **`StartIndex` on `reports/reportList` is a 1-based record
  offset**, so successive pages start at `1`, `1 + PageSize`, `1 + 2*PageSize` —
  the same quirk `search/items` has, but with sharper edges: `StartIndex=0`
  returns **HTTP 500** here, and on `reports/log` it silently returns
  `PageSize - 1` records, dropping one. Paging from a 0-based offset therefore
  either errors or loses records, depending on the endpoint.
- Reuse the existing filer resolution from `resolve.py` for `<filer>`, so
  `ocpf reports Matewsky` and `ocpf reports 14819` both work exactly as they do
  for `ocpf filer` and `ocpf expenditures`.
- Treat a report type or date filter that matches nothing as a **successful empty
  result** (exit zero), per the existing `cli-foundation` contract. An
  unresolvable filer, an unknown report id, or an API failure stays non-zero.
- Report id validation is explicit, because the API's failure modes are
  misleading: `report/{id}` returns **HTTP 400 for any id below 39** and **HTTP
  500 for a well-formed id that does not exist** — never a 404. The command SHALL
  translate both into a plain "no such report" message rather than surfacing a
  raw server error that implies an OCPF outage.
- Record the report-endpoint contract in the project's API reference notes
  (`CLAUDE.md`): the log-vs-reportList tradeoff, the required `BaseReportTypeId`,
  the 1-based `StartIndex` and its two distinct failure modes, the 400/500
  not-found behavior, and the working `reports/log?Name=` search.

Out of scope for this change, deliberately:

- **Downloading the PDF.** `report/pdf/{reportId}` works and returns
  `application/pdf`, but binary transport and writing files to disk are a new
  capability class for `api.py`, which is JSON-only by design. Instead both
  commands SHALL surface the report's canonical web link (`reportLink` /
  `ocpfUsReportLink`), which makes fetching the PDF a one-line `curl` away. A
  later change can add `--pdf`.
- **Widening filer name resolution to `reports/log?Name=`.** The discovery that
  this endpoint performs a case-insensitive partial match across *all* filers,
  not just the legislative field, is significant — it is a potential answer to
  the long-standing "non-legislative filers are only reachable by cpfId"
  limitation. But changing `resolve.py` changes the contract of three existing
  commands and belongs in its own change with its own ambiguity rules.
- **Cross-filer report search.** `reports/log` accepts `ReportTypeId` and `Name`
  without a `CpfId`, and its filters fail *closed* (an unknown `ReportTypeId`
  returns an empty list, unlike `search/items`). Deferred here, but designed
  around rather than ignored, because it is the backbone of issue #3: sweeping
  `ReportTypeId=23` (`Pre-election Report (Special)`) is 556 rows in two
  requests, and grouping those rows by their `officeSought` reconstructs
  district-scoped special-election rosters for exactly the years the on-ballot
  feeds return nothing — House 6th Bristol 2013 yields Fiola (13597) and
  Steinhof (15658), Senate 1st Suffolk yields Forry (14359) and Ureneck (14412),
  Senate 2nd Hampden & Hampshire yields Bartley (12646) and Humason (13888),
  each matching the cpfIds that issue names. It also recovers Leah Cole (15567)
  and Daniel M. Donahue (15637), the two candidates a cross-year name index
  matched to the wrong people. That is a roster question, not a report question:
  it belongs with `race-summary`, and it needs district-name normalization that
  issue #4 is about. Deferring it keeps this change to the filer-to-report path
  that issue #3 asks whether exists — it does: `reports/baseReportTypes/{cpfId}`
  plus `reports/reportList/{cpfId}`, no roster involved.
- **Report diffs.** `report/diffs/{reportId}` and the `diffs` arrays on each line
  item expose what an amendment changed. Worth having; not needed to read a
  filing.
- **Cross-filer discovery via `reports/log`.** The log stays useful for
  questions the per-filer listing cannot answer, and this change does not use it.
  See "Cross-filer report search" above.

## Capabilities

### New Capabilities
- `report-list`: The `ocpf reports <filer>` command — filer resolution, the
  paginated `reports/log` retrieval and its completeness contract, the report
  type and date filters, the rendered listing, the empty-result contract, and
  `--json`.
- `report-detail`: The `ocpf report <report-id>` command — retrieval of a single
  filing from `report/{reportId}`, the rendered header and schedule totals, the
  optional per-schedule line-item views, amendment lineage and the canonical
  report link, the not-found contract for invalid and nonexistent ids, and
  `--json`.

### Modified Capabilities

None. `filer-lookup`'s "Recent filing log" requirement stays as written —
`ocpf filer` continues to show a short recency-ordered excerpt drawn from
`filer/payload`, and `ocpf reports` is the full, filterable index. `cli-foundation`
already covers the exit-code contract these commands need, including the
carve-out for a filter that matches nothing.

## Impact

- **New code**: `src/ocpf_cli/reports.py` holding the report-endpoint client
  (base-report-type discovery, paged `reports/reportList` retrieval with 1-based
  `StartIndex`, single-report fetch, and the not-found translation);
  `src/ocpf_cli/commands/reports.py` holding both subcommands; both registered in
  `cli.py`.
- **Reused foundation**: `api.get_json` / `OcpfApiError`, `resolve.resolve_filer`,
  and `render` for tables, JSON emission, and currency. Monetary values arrive as
  display strings (`"$1,430.30"`) and dates as `M/D/YYYY`, the same shapes
  `expenditure-search` already parses — the parsing helpers should be shared
  rather than reimplemented.
- **External API**: read-only GETs. A listing is one request to discover base
  report types plus one per type — two requests for a non-depository filer, eight
  for a twenty-year depository committee, with a `PageSize` large enough that no
  type needs a second page. A detail view is exactly one request.
- **Docs**: `CLAUDE.md` gains a report-endpoints section and two corrections to
  its existing API notes — `reports/reportList/{cpfId}` is reclassified from
  broken to "requires `BaseReportTypeId`", and the blanket claim that free-text
  filer name search is dead is narrowed to exclude `reports/log?Name=`. The
  sibling repo's `../ocpf-analysis/api/ENDPOINT-STATUS.md` is not edited by this
  change.
- **Tests**: base-type fan-out and merge, `reportList` paging (including that a
  0-based offset is a bug), the `OnlyCurrent` default and its flag, filter
  behavior, empty results, the 400 and 500 not-found paths, and rendering of a
  report with and without each schedule. Fixtures should be trimmed captures of
  report 170378 and of `reports/reportList/14819?BaseReportTypeId=8`.
- **No breaking changes**: purely additive. No existing command's behavior or
  output changes.
