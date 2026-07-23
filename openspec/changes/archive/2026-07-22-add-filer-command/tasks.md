## 1. Shared feed-merge helpers

- [x] 1.1 Factor `fetch_merged_field` and `_reports_of` out of `commands/race.py` into a shared module (e.g. `legislative.py`) importable by both commands, or confirm importing from `race` stays clean; keep `ocpf race` behavior unchanged
- [x] 1.2 Run the existing test suite to confirm `race` still passes after the refactor

## 2. Filer resolution (filer-lookup)

- [x] 2.1 Implement filer resolution in `commands/filer.py`: a bare integer argument is used directly as a `cpfId`
- [x] 2.2 For a non-numeric argument, fetch the merged legislative field for `--year` and match case-insensitively against each row's `filerName`
- [x] 2.3 Handle zero matches (error + hint to pass a cpfId, non-zero exit), one match (use its `cpfId`), many matches (print candidates with cpfId + office, exit) without guessing
- [x] 2.4 Test resolution: numeric passthrough, unique name match, ambiguous name (multiple candidates), and no-match cases with fixture field data

## 3. Filer fetch (filer-lookup)

- [x] 3.1 Fetch `filer/payload/{cpfId}` via the shared API client, extracting `filer`, `ytdReport`, and `logReports`
- [x] 3.2 Handle an unknown/empty cpfId (no filer found → clear message, non-zero exit) and map API/HTTP failures to `OcpfApiError` without leaking raw exceptions
- [x] 3.3 Read payload fields defensively with `.get(...)` so a missing optional field never crashes rendering

## 4. Filer rendering (filer-lookup)

- [x] 4.1 Render the profile header: committee name, candidate name, party, office sought/held, active/closed status (+ closed date when present), organization date, treasurer
- [x] 4.2 Render the YTD line: cumulative receipts, expenditures, and cash on hand as formatted currency with the as-of `bankReportEndDate`; never split by election
- [x] 4.3 Render the recent-reports table: report type, reporting period, date filed, receipt total, expenditure total; show a "no reports found" message when empty
- [x] 4.4 `--json` output: emit `filer`, `ytdReport`, and `logReports` (including numeric values) as JSON-only on stdout, human status to stderr

## 5. CLI wiring (filer-lookup)

- [x] 5.1 Implement `filer(filer, --year default current year, --json)` in `commands/filer.py`, wiring resolution → fetch → render
- [x] 5.2 Register the `filer` subcommand in `cli.py` alongside `race`
- [x] 5.3 Smoke-test `ocpf filer --help` and confirm `race` and `filer` both appear under `ocpf --help`

## 6. Verification and docs

- [x] 6.1 End-to-end: `ocpf filer 14454` shows Brownsberger's profile, YTD finances, and recent reports; `ocpf filer "Brownsberger" --year 2026` resolves by name to the same filer
- [x] 6.2 Verify `--json` output is valid JSON, stdout-only, and includes numeric monetary values
- [x] 6.3 Run the full test suite (green) and update `README.md` with the `ocpf filer` usage and an example
