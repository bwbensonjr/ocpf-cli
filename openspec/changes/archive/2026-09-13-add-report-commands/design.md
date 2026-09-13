## Context

See proposal.md — Why. The constraints that shape the approach, all verified
against the live API during this change's research (report 170378, cpfId 14819
Matewsky, cpfId 14454 Brownsberger):

- **Two endpoints can back a report listing, and they are not equivalent in
  shape.** `reports/log?CpfId=` is one request and returns every report type in a
  flat list, but its rows are built for a web table: `reportingPeriod` arrives in
  at least three incompatible shapes across 564 sampled rows — `7/1/19 - 12/31/19`
  (range, two-digit years), `9/1 - 9/30/2026` (abbreviated start, no year on the
  left side), and a bare `1/13/26` with no range at all — and `amendmentDisplay`
  carries literal HTML (`<br>Amendment`). `reports/reportList/{cpfId}` returns the
  same filings with structured `startDate`, `endDate`, integer `reportYear`,
  `startBalance`/`endBalance`, and boolean `isAmendment`/`isAmended` alongside
  `previousReportId`/`nextReportId`.
- **`reportList` requires `BaseReportTypeId` and accepts only one value.** Without
  it: HTTP 400, `"No base report type ID was provided"` — which is why the
  project's API notes currently list the endpoint as broken. A comma-separated
  value returns an empty body; a repeated parameter silently uses the first. So a
  complete listing needs `reports/baseReportTypes/{cpfId}` first, then one call
  per type. That fan-out is bounded: seven types for a twenty-year depository
  committee, one for a non-depository committee.
- **The two sources agree exactly.** Summing `reportList` across cpfId 14454's
  seven base report types with `OnlyCurrent=false` gives 517; `reports/log` for
  the same filer gives 517. The fan-out loses nothing.
- **`OnlyCurrent` defaults to true.** For cpfId 14819, base type 8:
  `OnlyCurrent=true` (and the default) returns 21, `OnlyCurrent=false` returns 47.
  The extra 26 are superseded versions of amended filings.
- **`StartIndex` is a 1-based record offset**, not a page number. On `reportList`,
  `StartIndex=0` returns HTTP 500; `StartIndex=1` and `StartIndex=2` return
  overlapping windows (`[a,b,c]` then `[b,c,d]`). Correct paging is
  `1, 1+PageSize, 1+2*PageSize`. `search.py` already carries this same hazard for
  `search/items`; this is the second endpoint family with it.
- **`report/{reportId}` has no 404.** An id below 39 returns HTTP 400; a
  well-formed id that does not exist returns HTTP 500 with an empty body
  (`report/99999999`). Only a valid id returns 200.
- **Existing seams**: `api.get_json(path, params)` raising `OcpfApiError`;
  `resolve.resolve_filer` shared by `filer` and `expenditures`; `render` for
  tables, JSON emission, and currency; `search.py` as the precedent for a module
  that hides an endpoint's hazards behind a typed function.

## Goals / Non-Goals

**Goals:**

- A report client whose output is structured data, so that date and year
  filtering never depends on parsing a display string.
- Retrieval that is complete across base report types or loudly incomplete —
  never quietly partial because one type's second page was missed.
- A not-found contract that distinguishes "this report does not exist" from "OCPF
  is down", despite the API using the same status code family for both.

**Non-Goals:**

- Exposing base report types as a user-facing concept. They are a retrieval
  detail; users think in report *types* ("pre-election"), not in OCPF's internal
  grouping of them. See Decision 3.
- A general report query surface over all sixteen `reportList` parameters. Wire
  what the commands need.
- Reconciling a filing's totals against `ocpf filer`'s year-to-date figures.
  Per-filing and cumulative-annual are different quantities by construction.

## Decisions

### 1. `reportList` fan-out over the single-request log

Retrieve `reports/baseReportTypes/{cpfId}`, then one `reports/reportList/{cpfId}`
per returned `baseReportTypeId`, and merge.

*Alternative considered*: `reports/log?CpfId=` in one request. Rejected on data
shape, not on cost. The listing must support `--year`, `--since`, and `--until`,
and the log's only period field is a display string in three formats, one of
which (`9/1 - 9/30/2026`) omits the start year entirely and another (`1/13/26`)
is not a range. Deriving a filterable period from that means writing a parser
against undocumented formatting variants and being wrong for some filer whose
format was not in the sample. `reportList` hands over `startDate`, `endDate`, and
`reportYear` already parsed. Trading six HTTP requests for the removal of a
string-parsing guess is the right side of that trade, and the two sources were
verified to return identical report sets.

*Consequence*: the client must handle a filer whose `baseReportTypes` is empty.
cpfId 96054 returns `[]`. That is a filer with no reports, not an error condition
to retry — it maps to the spec's "filer has filed no reports" case.

*Scope of the rejection*: the log is rejected as the backbone of **this
per-filer listing**, not as a data source. It remains the only cross-filer path
in the API — `reportList` cannot be queried without a `cpfId` — and a sweep of
it by `ReportTypeId` reconstructs the district-scoped special-election rosters
that issue #3 needs (verified: 556 rows for `ReportTypeId=23`, yielding the
2013 rosters for House 6th Bristol, Senate 1st Suffolk, and Senate 2nd Hampden
& Hampshire with cpfIds matching that issue exactly). Its rows also carry
era-correct district names back to 2002, including districts retired at
redistricting — `Senate Worcester & Norfolk` is present under its own name,
which is the resolution failure issue #4 reports. When that work lands, the
display-string parsing this decision avoids becomes unavoidable and should be
confined to the log path rather than retrofitted onto the `reportList` rows
normalized here.

### 2. Paging: 1-based offset, per base type, with a duplicate guard

Each base type is paged independently: `StartIndex` starts at 1 and advances by
`PageSize`, using `withSummary=true` so `summary.count` gives the expected total,
stopping when the accumulated count reaches it. `StartIndex=0` is never emitted —
a named constant makes the 1-based start explicit rather than a bare `1` a future
reader might "fix" to `0`.

Because the endpoint's overlap failure mode is silent (a bad offset yields
plausible, duplicated rows rather than an error), retrieval additionally asserts
that no `reportId` appears twice in the merged result. A duplicate means the
paging arithmetic is wrong, and it raises rather than rendering an inflated
count. This is the report-side analogue of the assertion `search.py` makes about
record shape.

*Alternative considered*: requesting a `PageSize` large enough that paging never
happens (1000 covers every filer observed). Rejected as a latent bug — it works
until a filer exceeds it, and then it truncates silently. Page correctly and let
`PageSize` be a performance knob.

### 3. `--type` matches the report type *description*, not a numeric id

`reportList` and `reports/log` both accept a numeric `ReportTypeId`, but those ids
are undocumented and unstable to a user (23 is `Pre-election Report (Special)
(ND)`, 21 is `Pre-election Report (ND)`, 50 is the depository `Pre-primary
Report`). Filtering is therefore client-side, case-insensitive substring matching
against `reportTypeDescription`.

This choice has a deliberate, useful consequence: **the same report type has both
a depository and a non-depository spelling** — `Pre-Election Report (Special)` and
`Pre-election Report (Special) (ND)` — and `--type "pre-election"` matches both,
as does `--type "special"`. A user asking for pre-election reports wants them
regardless of which filing regime the committee was under. Matching on a numeric
id would return one and silently omit the other.

*Alternative considered*: an enum of known report types with server-side
`ReportTypeId`. Rejected: the enum would need maintaining against an undocumented
list, and it would answer a narrower question than the user asked.

### 4. Filtering is client-side, consistent with `expenditure-search`

`reportList` offers `ReportYear`, `ReportStartDate`, `ReportEndDate`,
`FilingStartDate`, and `FilingEndDate`. All filtering is nonetheless applied
locally to the merged result, for the same reason `expenditure-search` decided
this: on this API a misnamed or misinterpreted filter parameter is ignored rather
than rejected, and an ignored filter is indistinguishable from one that matched
everything. Locally applied filters are testable without a network and cannot
fail open. Retrieval volume is not a concern — the largest observed filer is 517
reports at roughly 3 KB each.

Date filters apply to the **reporting period** (`startDate`/`endDate`), not the
filing date. "Show me the reports covering the March 2013 special" is the
question; when the paperwork was submitted is a separate fact, displayed in its
own column. `--year` matches `reportYear`.

### 5. `ocpf reports` and `ocpf report` — flat commands, with near-miss handling

The CLI is flat (`race`, `filer`, `expenditures`); a nested `ocpf report list` /
`ocpf report show` group would break that. The cost is a singular/plural pair one
character apart.

That near-miss is handled explicitly rather than tolerated:
- `ocpf report <non-numeric>` fails with an error that names the likely intent:
  *"`<value>` is not a report id — did you mean `ocpf reports <value>`?"*
- `ocpf reports <numeric>` that resolves to no filer adds: *"if that was a report
  id, use `ocpf report <value>`."*

Both are already error paths the specs require; the wording is what makes the
pair safe. Tests assert the cross-reference text, because it is the mitigation.

### 6. One command module, two commands

Both commands live in `src/ocpf_cli/commands/reports.py`, deviating from the
project's one-command-per-module convention. Adjacent files named `report.py` and
`reports.py` are a maintenance hazard out of proportion to the convention they
would satisfy — an import or an edit landing in the wrong one is a silent
mistake. The two commands also share the report-type vocabulary, the schedule
names, and the currency/date coercion, so the split would be artificial.

The endpoint client stays separate in `src/ocpf_cli/reports.py`, mirroring how
`search.py` sits behind `commands/expenditures.py`.

### 7. Not-found translation happens in the client, once

`reports.fetch_report(report_id)` translates the API's two not-found signals into
a single typed `ReportNotFoundError`:
- ids below 39 are rejected **locally**, before any request, since the boundary is
  deterministic and there is no reason to spend a round trip on a guaranteed 400;
- an HTTP 500 from `report/{reportId}` is translated to not-found.

*Risk accepted*: OCPF returning a genuine 500 during an outage would be reported
as "no such report". Mitigated by wording the message so it does not overclaim —
it states that the API returned no report for that id and that the id may not
exist — and by leaving network failures, timeouts, and every other status as
ordinary `OcpfApiError`, so a real outage still surfaces as one on every other
code path including the listing command. A silent wrong answer is not possible in
either direction; only the phrasing of a rare failure is imprecise.

### 8. Schedules are opt-in and named in user vocabulary

`report/{reportId}` returns six line-item arrays. Report 170378 alone carries 20
receipts, 43 expenditures, 1 in-kind, and 10 liabilities — printing all of them by
default makes the common case ("what period does this cover and what were the
totals?") unreadable. `--schedule` is repeatable and takes user-facing names
(`receipts`, `expenditures`, `out-of-pocket`, `in-kind`, `liabilities`,
`subvendor`) mapped to the API's field names in one table, so an unknown name can
be rejected with the valid list.

### 9. Money and dates are coerced at the boundary

Every monetary field on both endpoints is a display string (`"$1,430.30"`) and
every date is `M/D/YYYY`, exactly as `search/items` returns them. The client
coerces at the boundary using the existing `render` helpers so that `--json`
emits numeric values — matching what `filer-lookup` and `expenditure-search`
already promise — and so that sorting and date filtering operate on real types.

### 10. The listing defaults to the filer's entire filing history

No implicit year default. `ocpf reports <filer>` with no filters lists every
report the filer has filed, most recent first, with the count at the bottom;
`--year`, `--type`, `--since`/`--until`, and `--limit` narrow it.

*Alternative considered*: defaulting to the current calendar year, matching how
`--year` already works in `race` and `filer`. Rejected because it makes the
motivating case invisible — a 2013 special-election filing would not appear until
the user already knew to ask for 2013, which is the thing they are trying to find
out. A long listing is a readability cost the user can fix with a flag; a
silently narrowed one is a wrong answer they cannot see.

*Consequence*: a twenty-year depository committee prints 517 rows, most of them
routine monthly deposit and bank reports. `--type` is the documented remedy and
the command's help text should say so.

## Risks / Trade-offs

- **Fan-out multiplies request count** → Bounded at 1 + N where N is the filer's
  base report type count (maximum 7 observed, 1 for a non-depository committee).
  Status output to stderr reports progress so a slow listing is not a silent
  hang.
- **A new base report type appears that the fan-out does not know about** →
  Non-issue by construction: the type list comes from the API per filer rather
  than from a hardcoded set, so a new type is picked up automatically.
- **`OnlyCurrent=false` output can confuse** → A filing amended twice appears
  three times. Default is current-only; superseded rows are explicitly marked
  when the flag is passed, and the spec requires the two be distinguishable.
- **A genuine OCPF outage could be reported as a missing report** → See Decision
  7. Accepted, with wording that does not overclaim.
- **`reportList` items are ~3 KB with roughly 100 fields, mostly unused** → 1.5 MB
  for the largest observed filer. Not worth optimizing; the alternative endpoint
  costs correctness.
- **The log's cross-filer power goes unused** → `reports/log` remains the right
  tool for "every pre-election special filed this cycle" and for the free-text
  `Name` search. Deliberately deferred in the proposal; this design does not
  foreclose it, and the report-row coercion written here is reusable if it lands.

## Open Questions

None. The listing's default scope was the one open question and is settled in
Decision 10.
