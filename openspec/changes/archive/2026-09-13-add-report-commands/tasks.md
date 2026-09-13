## 1. Report endpoint client

- [x] 1.1 Add `src/ocpf_cli/reports.py` with a module docstring recording the
      endpoint contract from design.md — `BaseReportTypeId` is required (HTTP 400
      without it, empty body for a comma-separated value, first-wins for a
      repeated one), `StartIndex` is a 1-based record offset (HTTP 500 at 0),
      `OnlyCurrent` defaults to true, and `report/{id}` has no 404 — each with the
      verified observation that establishes it; verify the file imports cleanly
      and `uv run pytest` still passes.
- [x] 1.2 Implement `fetch_base_report_types(cpf_id)` over
      `reports/baseReportTypes/{cpfId}` returning the id/description pairs, with
      an empty list returned as an empty result rather than an error; verify with
      a respx-mocked `[]` response (the real behavior of cpfId 96054) that the
      call returns empty and does not raise.
- [x] 1.3 Implement paged retrieval for one base report type against
      `reports/reportList/{cpfId}` using `withSummary=true`, a named
      `START_INDEX_BASE = 1` constant, and offsets advancing by `PageSize`;
      verify with a mocked three-page response that every record is returned,
      that the first request sends `StartIndex=1`, and that no request ever sends
      `StartIndex=0`.
- [x] 1.4 Raise `OcpfApiError` when the accumulated count falls short of
      `summary.count` or when a page returns zero new items; verify with mocked
      short and stalled responses that each raises rather than returning a
      partial set.
- [x] 1.5 Implement `fetch_reports(cpf_id, *, include_superseded=False)` that
      fans out across every base report type, passes `OnlyCurrent` from the flag,
      merges the results, and asserts no `reportId` appears twice — raising
      `OcpfApiError` on a duplicate; verify with a mocked two-type fixture that
      the merge is complete and with an overlapping-page fixture that the
      duplicate guard raises (design Decision 2).
- [x] 1.6 Coerce each merged row at the boundary: numeric values from the
      `"$1,234.56"` display strings via `render.parse_currency`, and parsed dates
      from `startDate`, `endDate`, and `dateFiledDisplay`; verify unit tests cover
      `"$0.00"`, a negative or parenthesized value, and a malformed value.
- [x] 1.7 Implement `fetch_report(report_id)` over `report/{reportId}`, rejecting
      ids below 39 locally before any request and translating HTTP 500 into a
      typed `ReportNotFoundError`, leaving timeouts and other statuses as
      `OcpfApiError`; verify with mocked responses that id 38 raises without
      issuing a request, that a 500 raises `ReportNotFoundError`, and that a
      timeout raises `OcpfApiError` (design Decision 7).

## 2. `ocpf reports` listing command

- [x] 2.1 Add `src/ocpf_cli/commands/reports.py` with a `reports` command taking
      `<filer>`, resolving it through `resolve.resolve_filer`, and register it in
      `cli.py`; verify `uv run ocpf reports --help` lists the command and
      `uv run ocpf reports 14819` prints that filer's reports.
- [x] 2.2 Render the listing most-recent-first with report id, type, reporting
      period, date filed, receipts, and expenditures, followed by the count;
      verify against the real API that `uv run ocpf reports 14819` shows 21
      reports and includes report 170378 as `Pre-election Report (Special) (ND)`
      covering 2/16/2013 - 3/15/2013.
- [x] 2.3 Default to the filer's entire filing history with no implicit year
      filter, and mention `--type` in the command help as the remedy for a long
      listing; verify `uv run ocpf reports 14454` prints all 444 current reports
      (517 with `--include-superseded`) rather than only the current year
      (design Decision 10).
- [x] 2.4 Implement `--include-superseded`, passing `OnlyCurrent=false`, and mark
      amendment rows using `isAmendment`/`isAmended` so operative and superseded
      versions are distinguishable; verify against the real API that
      `uv run ocpf reports 14819` shows 21 reports and
      `uv run ocpf reports 14819 --include-superseded` shows 47.
- [x] 2.5 Implement client-side `--type` as a case-insensitive substring match on
      `reportTypeDescription`; verify with a fixture containing both
      `Pre-Election Report (Special)` and `Pre-election Report (Special) (ND)`
      that `--type "pre-election"` matches both spellings (design Decision 3).
- [x] 2.6 Implement `--year`, `--since`, `--until` against the reporting period
      (`reportYear`, `startDate`, `endDate`) and `--limit` with an indication
      that the listing was limited; verify unit tests cover an inclusive boundary
      date at each end and that `--year 2013` on cpfId 14819 returns only the
      2013 filings.
- [x] 2.7 Report a filter that matches nothing on stdout naming what was filtered
      on, exiting zero, and a filer with no reports at all on stderr exiting
      non-zero; verify both exit codes with `uv run ocpf reports 14819 --type
      "nonexistent"; echo $?` returning 0 and a no-reports fixture returning
      non-zero.
- [x] 2.8 Add `--json` emitting the resolved filer and matching reports with
      numeric money, each report's id, type, period, date filed, totals, and
      canonical link, and no human output; verify
      `uv run ocpf reports 14819 --json | python3 -m json.tool` parses and that
      the empty-filter case emits a valid document with an empty result set.

## 3. `ocpf report` detail command

- [x] 3.1 Add a `report` command taking a numeric `<report-id>` in the same
      module and register it in `cli.py`; verify `uv run ocpf report 170378`
      prints that filing and exits zero.
- [x] 3.2 Render the header — report type, reporting period, date filed,
      committee, candidate, office and district sought, treasurer, bank; verify
      against the real API that report 170378 shows `Pre-election Report
      (Special) (ND)`, `2/16/2013 - 3/15/2013`, `Matewsky Committee`, and
      `House, 28th Middlesex`.
- [x] 3.3 Render the schedule totals — start balance, itemized and unitemized
      receipts and expenditures, in-kind, liabilities, end balance — as currency;
      verify report 170378 shows a start balance of $7,953.94 and an end balance
      of $1,430.30.
- [x] 3.4 Print the canonical OCPF report link from `ocpfUsReportLink`, and note
      in the command help that `report/pdf/{id}` serves the PDF; verify the link
      for 170378 appears in default output and in `--json`.
- [x] 3.5 Render amendment lineage from `isAmendment`, `isAmended`,
      `previousReportId`, and `nextReportId`, printing nothing when the filing is
      neither; verify report 170378 is marked as an amendment naming 170376, and
      that an unamended fixture prints no marker.
- [x] 3.6 Implement a repeatable `--schedule` taking user-facing names
      (`receipts`, `expenditures`, `out-of-pocket`, `in-kind`, `liabilities`,
      `subvendor`) mapped to the API fields, printing each as its own labeled
      section with date, amount, counterparty, and record type, and omitting all
      line items by default; verify `uv run ocpf report 170378 --schedule
      expenditures` prints 43 rows and that the default output prints none
      (design Decision 8).
- [x] 3.7 Report an empty requested schedule as empty exiting zero, and an
      unrecognized schedule name with an error listing the valid names exiting
      non-zero; verify `--schedule out-of-pocket` on 170378 reports empty with
      exit 0 and `--schedule bogus` exits non-zero naming the valid set.
- [x] 3.8 Surface `ReportNotFoundError` as a plain not-found message that does
      not overclaim an outage, and a non-numeric id as an argument error; verify
      `uv run ocpf report 99999999` and `uv run ocpf report 1` both report no
      such report and exit non-zero, and that a timeout still reports as an API
      error.
- [x] 3.9 Add `--json` emitting the header, period, totals, amendment lineage,
      link, and the line items of any requested schedules, with numeric money and
      no human output; verify `uv run ocpf report 170378 --json --schedule
      receipts | python3 -m json.tool` parses and contains 20 receipt items.

## 4. Command near-miss handling

- [x] 4.1 Make `ocpf report <non-numeric>` fail with an error naming the likely
      intent ("did you mean `ocpf reports <value>`?"); verify a test asserts the
      cross-reference text, since the wording is the mitigation for the
      singular/plural pair (design Decision 5).
- [x] 4.2 Make `ocpf reports <numeric>` that resolves to no filer add "if that
      was a report id, use `ocpf report <value>`"; verify a test asserts the
      cross-reference text and the non-zero exit.

## 5. Documentation and release

- [x] 5.1 Update the OCPF API reference in `CLAUDE.md` with a report-endpoints
      section covering the fan-out, the required `BaseReportTypeId`, the 1-based
      `StartIndex` and its two failure modes, `OnlyCurrent`, and the 400/500
      not-found behavior; verify the section states that report access goes
      through `reports.py` rather than `api.get_json` directly, matching how
      `search.py` is documented.
- [x] 5.2 Correct the two stale claims in `CLAUDE.md`: reclassify
      `reports/reportList/{cpfId}` from broken to requiring `BaseReportTypeId`,
      and narrow "free-text filer name-search endpoints are dead (404)" to
      exclude `reports/log?Name=`, which performs a case-insensitive partial match
      across all filers; verify by re-running the two calls cited in the note.
- [x] 5.3 Document both commands in `README.md` with the special-election example
      that motivated the change (`ocpf reports Matewsky --type "pre-election"`
      then `ocpf report 170378`); verify the commands in the README run as
      written against the live API.
- [x] 5.4 Add a CHANGELOG entry for the two new commands under an unreleased
      heading; verify it follows the format of the `ocpf expenditures` entry.
- [x] 5.5 Run `uv run pytest` and confirm the full suite passes with the new
      tests, including that no existing `race`, `filer`, or `expenditures` test
      required changes.
