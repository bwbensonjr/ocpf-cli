## 1. Cross-filer report sweep

- [x] 1.1 Add the special report-type constants to `src/ocpf_cli/reports.py`
      (pre-primary special and pre-election special, each covering the
      non-depository and depository spellings that share a `ReportTypeId`), with
      a comment recording that `reports/log` filters fail closed — an unknown
      `ReportTypeId` returns `[]`; verify by re-running the two calls cited.
- [x] 1.2 Implement a paged `reports/log` sweep that fetches every row for a
      report type, using the same 1-based `START_INDEX_BASE` the module already
      defines; verify with a mocked three-page response that all rows are
      returned, that the first request sends `StartIndex=1`, and that none sends
      `StartIndex=0`.
- [x] 1.3 Verify against the live API that the sweep returns 563 rows for
      `ReportTypeId=22` and 556 for `ReportTypeId=23`, in two requests each at
      `PageSize=500`.
- [x] 1.4 Parse a sweep row's `reportingPeriod` into a real start and end date,
      handling the two-digit-year range form, and ignore `amendmentDisplay`
      entirely (amendment resolution happens via `OnlyCurrent` in group 2);
      verify unit tests cover `7/27/13 - 8/23/13`, a four-digit-year range, and
      an unparseable value, and that no display string escapes the sweep (design
      Decision 2).
- [x] 1.5 Memoize the sweep for the life of an invocation so selecting a stage
      does not refetch; verify with a mocked API that two roster lookups in one
      process issue the sweep requests once.

## 2. Roster assembly

- [x] 2.1 Group sweep rows by `officeSought`, parsing it with the existing
      `districts._parse_office_sought` helper and discarding non-legislative
      offices; verify a fixture containing a `Municipal, Worcester` row leaves it
      out of any legislative roster (spec: "Non-legislative offices are
      excluded").
- [x] 2.2 Match a resolved district to its sweep rows by normalized description,
      reusing `districts._normalize` so `"Worcester and Norfolk"` matches the
      sweep's `Senate Worcester & Norfolk`; verify with a fixture that the
      ampersand, comma and ordinal-word forms all match.
- [x] 2.3 Narrow rows to the requested year from the end of the parsed reporting
      period, and group the survivors by stage; verify against the live API that
      House 6th Bristol 2013 yields Fiola (13597) and Steinhof (15658) among its
      pre-election special filers, and Senate 1st Suffolk yields Forry (14359)
      and Ureneck (14412).
- [x] 2.4 Report a district and year with no special-election filings as an error
      naming both, exiting non-zero; verify with a district that held no special
      (spec: "District has no special election that year").

## 3. Stage selection

- [x] 3.1 Add `--special` and `--stage primary|general` to `ocpf race` as a Typer
      enum, branching before the legislative-feed fetch; verify
      `uv run ocpf race --help` lists both and that `--stage bogus` is rejected
      before any request.
- [x] 3.2 With no `--stage`, use the general when both stages are present and the
      only stage when one is; verify House 6th Bristol 2013 (which holds both)
      resolves to the general without error and notes the primary, and that a
      general-only district-year resolves without the option (spec: "Both stages
      exist and no stage was given", "Only one stage exists").
- [x] 3.3 Span differing filing windows within one stage into one period rather
      than treating them as rival elections, taking the span from the operative
      filings and saying in the header when the windows differ; verify against
      the live API that Senate 1st Suffolk 2013 puts Forry (4/13-5/10) and
      Ureneck (4/23-5/20) in one roster (design Decisions 4 and 5).
- [x] 3.4 Report a requested stage that was not held, naming the stage that was;
      verify with a fixture holding only a primary that `--stage general` exits
      non-zero and names the primary.

## 4. Money from the operative filing

- [x] 4.1 For each roster candidate, fetch their reports via
      `reports.fetch_reports(cpf_id)` and select the operative report matching
      the stage's type and the year; verify against the live API that Steinhof
      (15658) yields report 199084 at $13,530.00 / $6,829.57 and Fiola (13597)
      yields report 180940 at $6,535.00 / $22,751.61.
- [x] 4.2 Add a regression test pinning that the money never comes from a
      superseded filing: with a fixture holding Steinhof's four generations
      ($9,940.00 as filed through $13,530.00 amended), the reported figure is
      $13,530.00; verify it fails if the sweep row's total is used instead (spec:
      "Amended filing reports the amended figures").
- [x] 4.3 Render a candidate with no operative report for the stage with their
      money marked as not reported, rather than dropping them or showing zero;
      verify with a fixture containing such a candidate (design Decision 6).

## 5. Rendering

- [x] 5.1 Render the special-election header with the district, the stage, and
      the reporting period the figures cover, and assert no election date; verify
      against the live API that House 6th Bristol 2013 (defaulting to the
      general) shows the window `7/27/2013 - 8/23/2013` and prints no election
      date (spec: "Special-election header names a period, not a date").
- [x] 5.2 Render the candidate table with money columns labeled as the filing
      period's figures rather than year-to-date; verify the labels differ from
      the regular-cycle table's.
- [x] 5.3 Add `--json` output carrying each candidate's cpfId, numeric monetary
      values, the reporting period, and the operative report id each figure came
      from; verify the document parses and that the report ids match those in
      task 4.1.
- [x] 5.4 Make `ocpf race <district> --year <year>` name `--special` in its
      no-candidates error; verify `uv run ocpf race "6th Bristol" --year 2013`
      exits non-zero with a message naming the flag, and that
      `uv run ocpf race "6th Bristol" --year 2013 --special` then succeeds.

## 6. Regression and documentation

- [x] 6.1 Pin that the regular-cycle path is untouched: verify with a mocked API
      that `ocpf race` without `--special` issues exactly the requests it issued
      before this change and renders the same table, and that no existing race
      test required modification (design Decision 7).
- [x] 6.2 Record in `CLAUDE.md` the sweep contract — `reports/log` is the only
      cross-filer path, its filters fail closed, the special type ids and their
      row counts, the absence of server-side date and district filters, and the
      amendment hazard that makes sweep-row money unsafe; verify by re-running
      the calls cited.
- [x] 6.3 Document `--special` and `--stage` in `README.md` with the 2013 6th
      Bristol example, noting that the roster is who *filed* rather than who
      appeared on a ballot, and that a stage's money covers that stage's window
      rather than the whole campaign; verify the documented commands run as
      written.
- [x] 6.4 Add a CHANGELOG entry under an unreleased heading.
- [x] 6.5 Run `uv run pytest`, and run it again under `CI=true
      GITHUB_ACTIONS=true`, confirming both pass — rich styles CLI error text
      differently under that environment, which has broken a pull request in this
      repo before.
