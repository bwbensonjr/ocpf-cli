## Context

See proposal.md — Why. The constraints that shape the approach, verified against
the live API:

- **`reports/log` is the only cross-filer path.** `reports/reportList` cannot be
  queried without a `cpfId`, and the on-ballot and legislative feeds carry no
  special elections at all. The log's filters fail *closed* — an unknown
  `ReportTypeId` returns `[]` rather than the whole database, unlike
  `search/items`.
- **The special report types are small and sweepable.** `ReportTypeId=22`
  (pre-primary special) is 563 rows and `23` (pre-election special) is 556, two
  requests each at `PageSize=500`. Rows carry `cpfId`, `fullNameReverse`,
  `officeSought`, `reportingPeriod`, `receiptTotal`, `expenditureTotal`,
  `amendmentDisplay` and `reportLink`. Both the non-depository and depository
  spellings appear under the same id (`Pre-election Report (Special) (ND)` and
  `Pre-Election Report (Special)`).
- **The log has no server-side date or district filter.** `StartIndex`,
  `PageSize`, `Name`, `CpfId`, `ReportTypeId`, `ReportTypeCategory` is the whole
  list, so year and district narrowing happen locally.
- **The log's rows are display strings.** `reportingPeriod` arrives in at least
  three shapes across the wider log (`7/1/19 - 12/31/19`, `9/1 - 9/30/2026` with
  no start year, a bare `1/13/26` that is not a range) and `amendmentDisplay`
  holds literal HTML (`<br>Amendment`). `reports.py` documents this and the
  per-filer path avoids it by using `reportList`; the sweep cannot.
- **Money on a sweep row is unreliable.** Steinhof (15658) filed four
  pre-election special reports for 7/27/2013-8/23/2013: `$9,940.00` as filed,
  then `$13,030.00`, then `$13,530.00` twice. The sweep returns all four.
- **`reports.fetch_reports(cpf_id)` already solves that**, defaulting to
  `OnlyCurrent=true`: it returns exactly one operative pre-election special
  report for Steinhof, at the amended `$13,530.00`.
- **There is no special election date to display.** `filingSchedules/2013`
  returns empty strings for `primaryElectionDate` and `generalElectionDate`.
- **Existing seams**: `districts.resolve_district(query, year)` is year-aware as
  of the district-resolution change; `reports.fetch_reports` and its paging live
  in `reports.py`; `render` handles tables, currency and JSON.

## Goals / Non-Goals

**Goals:**

- Make the invocation from issue #3 work, for even years as well as odd.
- Report special-election money that belongs to the special election.
- Keep the regular-cycle path byte-identical, in behavior and in request count.

**Non-Goals:**

- A general cross-filer report search. See the proposal.
- Splitting a regular cycle's money at the September primary.
- Any claim about an election date, or about which candidates appeared on a
  ballot as opposed to filing for one. The API knows who *filed*; that is what is
  reported.

## Decisions

### 1. Sweep for the roster, per-filer lookup for the money

Two stages, because the endpoint that can answer "who ran" cannot be trusted for
"how much":

1. Sweep `reports/log` for the special report types, group rows by
   `officeSought`, and narrow to the requested district and year locally. This
   yields cpfIds and names.
2. For each cpfId, call `reports.fetch_reports(cpf_id)` and take the operative
   report matching the stage and year.

*Alternative considered*: reading `receiptTotal`/`expenditureTotal` straight off
the sweep rows, which would make the whole command four requests. Rejected
because it is wrong, not merely coarse — the sweep returns every amendment
generation and picking the wrong row understates Steinhof by 36%. The second
stage costs one request per candidate on a roster of two to eight.

*Consequence*: the command's cost is `4 + N` requests. Acceptable, and the sweep
is memoized for the invocation so `--stage` does not double it.

### 2. Display-string parsing is confined to the sweep

The log's `reportingPeriod` and `amendmentDisplay` need parsing that the rest of
`reports.py` was explicitly built to avoid. That parsing lives in the sweep
functions and its outputs are normalized immediately into real dates, so nothing
downstream sees a display string. The module docstring already warns against
retrofitting it onto the `reportList` rows; this decision is the other half of
that warning.

The sweep does not need `amendmentDisplay` at all — amendment resolution happens
in stage 2 via `OnlyCurrent` — so the HTML field is ignored rather than parsed.
Only `reportingPeriod` is parsed, and only to extract the year and the window.

### 3. The stage maps to a report type, not to a date

`--stage primary` selects the pre-primary special report types and
`--stage general` the pre-election ones. This is exact: the distinction is
recorded in the filing itself rather than inferred from a calendar. It also
means the two stages are discovered, not assumed — a district that held only one
stage simply has rows of only one type, which is what lets the option be omitted
in the common case.

*Alternative considered*: selecting by election date. Rejected in two steps —
the API publishes no special election date, so the CLI could neither display nor
validate one, and deriving a date from the filing window would present a guess as
a fact.

### 4. Year comes from the reporting period, and the period is the header

A sweep row belongs to a year if its reporting period falls in that year. The
same period, rendered, is what the header shows in place of an election date.
This keeps one source of truth for "which election is this" and means the header
asserts nothing the data does not contain.

Candidates in one special election routinely file *different* windows for it:
43 of the 65 pre-primary district-years in the sweep carry more than one
distinct period, and merging overlapping windows collapses every one of them to
a single election. A depository filer's window and a non-depository filer's
simply begin on different days. So differing windows are spanned rather than
treated as rival elections, and the header says when it is spanning.

The span is taken from the operative filings the figures came from, not from the
sweep rows, so the period in the header describes exactly the money in the
table. Each candidate's own window is carried in `--json`, where the difference
is a fact a consumer may need.

### 5. The general is the default stage; genuine ambiguity is still reported

A district-year holding both stages is the common case, not the exceptional one:
of the 80 legislative district-years in the sweep, 64 hold both, 6 hold a primary
only and 10 a general only. Requiring `--stage` whenever both are present would
make an error of the ordinary invocation — including the one issue #3 reports,
since House 6th Bristol 2013 holds a pre-primary window (7/1/2013-7/26/2013) as
well as the pre-election one.

So a special's two stages are not treated as two elections to choose between.
They are two filing windows of one contest, and with no `--stage` the command
summarizes the general — the election itself — while reporting that a primary was
also held and naming the flag that reaches it. Nothing is hidden and nothing is
guessed: the header names the window the figures cover, so the narrower reading
of the number stays visible.

No second ambiguity remains to report. The plan had also treated two distinct
reporting periods within one stage as two special elections to choose between,
but that describes nothing in the data (Decision 4): differing windows are how
one election's filers file, and the only two district-year-stages whose windows
do not overlap — House 1st Suffolk 2015 and House 12th Suffolk 2005 — are single
elections too. A check for it would fire on real, unambiguous races, so there is
none.

*Alternative considered*: rendering both stages together in one summary.
Rejected because the money columns would then mean different windows in
different sections of one table, which is the conflation the period label exists
to prevent.

### 6. A missing filing is shown, not hidden

A candidate in the roster with no operative report for the requested stage is
rendered with their money marked as not reported. Dropping them would misstate
the field; showing zero would misstate their fundraising. This case is real —
candidates who file for a special primary and not its general appear this way.

### 7. The regular path is untouched

`--special` branches before the legislative-feed fetch, so the regular-cycle path
executes the same code and the same requests it did before. The spec pins this
("Regular-cycle behavior is unchanged"), and it is the claim most worth a test,
since this change edits a command that already works.

## Risks / Trade-offs

- **The sweep is unfiltered and grows over time** → ~1,100 rows today across both
  types, four requests. It grows by roughly one row per special-election filing,
  so the paging must be correct rather than incidental; the 1-based `StartIndex`
  trap applies here as everywhere on this API.
- **"Who filed" is not exactly "who was on the ballot"** → A candidate who filed
  for a special and withdrew appears in the roster. The command reports filings,
  the header says so, and no winner is claimed. This is why the special roster
  for House 6th Bristol 2013 holds five candidates where a ballot-based table
  holds two: the primary field is larger than the general field, and both are
  true answers to different questions.
- **Money is per-stage, not cumulative through the election** → A candidate's
  pre-election special filing covers the window since their pre-primary filing,
  not the whole campaign. Showing one stage's figure as "raised for this
  election" would understate it. The header names the period so the figure is
  never read as a campaign total, and `ocpf totals --start/--end` remains the way
  to get a cumulative window.
- **Local narrowing after a full sweep** → The whole type is fetched to answer a
  one-district question. Unavoidable: the endpoint has no district or date
  filter, and a filter it does not understand would be ignored rather than
  rejected.

## Open Questions

None. The two decisions that could have changed the specs — the selector shape
and what the money column means — were settled before this was written.
