## Context

See `proposal.md` — Why, for the defect and the measured evidence.

The constraint that shapes everything here is which OCPF fields are
era-correct. Three sources can associate a district with a name, and only the
third is tied to a year:

| source | gives | tied to a year? |
|---|---|---|
| `districts` | code + name | no — strictly the present map |
| `filer/{cpfId}.officeSought` | code + name | no — the filer's **most recent** office |
| a filing's `officeSought` | name only | **yes** — as of the filing |

Tier 4 already exploits a fourth, implicit one: the URL
`onballot/finsummaries/{year}/{code}` ties a *code* to a year by construction. So
tier 4 always knows the code for the year and is only ever missing the name. Today
it gets the name from `filer/{cpfId}`, which is not era-correct, and covers for
that by discarding filers whose reported code no longer matches. When the discard
empties the tally the tier gives up, even though the era-correct source exists.

`reports.py` already reaches that source. `fetch_report_log` pages `reports/log`
with the 1-based `StartIndex` and the short-page termination signal, and
`parse_reporting_period` turns the log's several display shapes into real dates.
Both are currently reachable only through the `ReportTypeId` path built for the
special-election sweep.

## Goals / Non-Goals

**Goals:**

- Make tier 4 resolve a district whenever `finsummaries` has a populated roster
  for it in the requested year, independent of whether its candidates ran again.
- Leave every lookup that succeeds today byte-identical in result and in request
  count.
- Keep the era-correct/not-era-correct distinction visible in the code, so the
  next person does not reintroduce a most-recent-office read as if it were a
  historical record.

**Non-Goals:**

- Replacing the filer tally. It is cheaper and it is right whenever it answers.
- Generalizing `reports/log` access beyond what this needs. A cpfId filter is one
  more parameter, not a new subsystem.
- Reconciling names between sources. `_normalize` already folds `&`/`and` and
  ordinal words, which is the only reconciliation the matching needs.

## Decisions

### Name from the filings, not from a second most-recent-office read

**Decision:** when the filer tally is empty, name the code from the
`officeSought` strings on the roster's filings for the requested year.

The alternative — relaxing the `districtCode != code` discard and letting a
moved-on filer label the seat — is wrong and already known to be wrong: Brady and
Diehl both now report 169, and an unfiltered tally would label district 128 with
their current seat. The discard is the thing standing between tier 4 and a
confidently wrong answer; it stays.

A second alternative — trusting the requested name because the roster is
populated — inverts the tier's job. Tier 4 is asked "which code is named X in year
Y" and must not answer "the one you asked about."

### Filter `reports/log` by cpfId, one filer at a time

**Decision:** query `reports/log?CpfId={id}` per roster filer, rather than
sweeping report types and grouping.

`reports/log` has no district filter and no date filter, so the only alternative
is sweeping whole report types and grouping locally — which is what the
special-election tier does, and it is affordable there only because the special
types are small (563 and 556 rows) and memoized. The general report types are not
small. A cpfId-filtered query is bounded by one filer's filing history: 331 rows
for cpfId 11448, one page at the existing `PAGE_SIZE` of 500.

`reports/log` filters fail **closed** — an unknown `ReportTypeId` returns `[]`,
not the unfiltered database — so a mistyped filter here yields an empty answer
rather than a plausible wrong one. This is the opposite of `search/items` and is
why this is safe to do per filer without a verification read-back.

**Implementation shape:** generalize `_fetch_log_page` to take a parameter dict
instead of a bare `report_type_id`, leaving `fetch_report_log(report_type_id)` as
a thin caller so the special-election path is untouched. The 1-based `StartIndex`
(`StartIndex=0` silently returns `PAGE_SIZE - 1` rows), the short-page
termination and the `MAX_PAGES` guard all come along unchanged.

### Match the year by reporting period, not by a year field

**Decision:** select a filer's rows for the requested year with
`parse_reporting_period`, the parser already used at the sweep boundary.

The log's `reportYear` is not reliably present on these rows — the live response
for cpfId 11448 returns `None` for it across all 331 rows — while
`reportingPeriod` is populated and already parsed into real dates. Reusing the
parser also keeps the log's display-string handling confined to `reports.py`, as
the module contract requires.

A filing whose period spans a year boundary is counted for the year its period
**ends** in, matching how the special-election tier already groups
(`row.period.end.year`).

### Tally across the roster; require agreement with nothing else

**Decision:** tally the era-correct office strings across all the roster's
filers for that year and take the most-reported, mirroring the filer tally's
rule.

Per-filer log rows for one year can still disagree — a candidate who switched
seats mid-year files under both — so a single filer's rows are not authoritative.
Tallying across the roster makes the seat the roster actually contested win.
Rows whose office string is not legislative are dropped, as elsewhere.

### Money and amendment state are never read here

**Decision:** take only `officeSought` and `reportingPeriod` from log rows.

The log returns every amendment generation of a filing, so a row's totals
identify a *version*, not a candidate — the documented 36% understatement for
cpfId 15658. Amendments are harmless for this purpose (every generation of a
filing carries the same office string), which is precisely why the office string
is safe to read where the money is not. Money continues to come from
`finsummaries`.

## Risks / Trade-offs

- **Extra requests on the failing path.** One `reports/log` request per roster
  filer, on top of the `filer/{cpfId}` lookup already made. Rosters are two to
  eight candidates → Mitigation: gate strictly on an empty tally, so codes that
  resolve today make no extra request at all. Tier 4 is already the lazy,
  expensive, last tier, and it currently spends that budget to produce a wrong
  answer.

- **The sweep probes many codes; a naive gating could fire the fallback on every
  one.** Most codes in the range are empty → Mitigation: the fallback is reached
  only after `finsummaries` returned a **populated** roster whose filers all
  moved on. An empty roster returns `None` before any log request, exactly as
  today.

- **A filer with a very long history pages more than once.** → Mitigation: the
  existing paging loop handles it; `MAX_PAGES` bounds it. 331 rows for a
  six-term senator suggests one page is the norm.

- **A seat may still be unnameable** if its filers filed nothing in the requested
  year. → Mitigation: this is a genuine absence of evidence, and the spec says
  what to do with it — do not assert the district did not exist. It also cannot
  be worse than today, where the same case already fails.

- **Two sources could disagree** about a seat's name for a year. → Mitigation:
  they are not consulted together. The filings are read only when the filer tally
  produced nothing, so there is no conflict to arbitrate.

## Migration Plan

None. Additive behavior on a path that currently errors; no data migration, no
config, no change to any output format. `District.code` is already `int | None`
from the previous change. Rollback is reverting the commit.

## Open Questions

None.
