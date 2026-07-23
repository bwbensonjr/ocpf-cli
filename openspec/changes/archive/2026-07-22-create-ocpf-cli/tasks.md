## 1. Project scaffolding

- [x] 1.1 Create the `uv` project: `pyproject.toml` with package `ocpf_cli` under `src/`, Python version pin, and dependencies (Typer, HTTP client)
- [x] 1.2 Define the `ocpf` console-script entry point pointing at `ocpf_cli.cli:app`
- [x] 1.3 Create the package layout: `src/ocpf_cli/{__init__,cli,api,render,districts}.py` and `src/ocpf_cli/commands/race.py`
- [x] 1.4 Add a `tests/` directory and configure the test runner (pytest) via `uv`

## 2. OCPF API client (cli-foundation)

- [x] 2.1 Implement `api.py` with `BASE_URL`, `get_json(path, params=None)` (GET + JSON parse + timeout), and a typed `OcpfApiError`
- [x] 2.2 Map HTTP 4xx/5xx to `OcpfApiError` carrying status code and requested path
- [x] 2.3 Map network/timeout failures to `OcpfApiError` with a clear message (no raw library exceptions leaking)
- [x] 2.4 Unit-test the client against mocked responses for success, HTTP error, and timeout

## 3. Output rendering (cli-foundation)

- [x] 3.1 Implement `render.py` table helper: aligned, labeled columns to stdout
- [x] 3.2 Implement JSON emission helper: valid JSON to stdout, only JSON on stdout when `--json` is set
- [x] 3.3 Route human status/progress messages to stderr so `--json` stdout stays pipeable
- [x] 3.4 Establish error/exit-code convention: clear stderr message + non-zero on failure, zero on success

## 4. CLI wiring (cli-foundation)

- [x] 4.1 Create the Typer `app` in `cli.py`; no-arg invocation and `--help` show help
- [x] 4.2 Register the `race` subcommand and a shared `--json` option
- [x] 4.3 Ensure unknown commands error clearly and exit non-zero
- [x] 4.4 Smoke-test `ocpf`, `ocpf --help`, and `ocpf <unknown>` behavior

## 5. District resolution (race-summary)

- [x] 5.1 Implement `districts.py`: fetch `districts`, filter to legislative (House/Senate) offices
- [x] 5.2 Accept a raw numeric code and validate it against the legislative set
- [x] 5.3 Implement case-insensitive name matching with `&`/`and`/whitespace normalization
- [x] 5.4 Handle zero matches (error), one match (proceed), many matches (print candidates + exit) without guessing
- [x] 5.5 Test the `Suffolk and Middlesex` (166) vs `Middlesex & Suffolk` (151) near-collision and the ambiguous `Middlesex` case

## 6. Legislative field fetch and merge (race-summary)

- [x] 6.1 Fetch `reports/legislative/depository/ytd/{year}` and take `.reports`
- [x] 6.2 Fetch the non-depository legislative feed for the year and take its reports
- [x] 6.3 Merge both feeds by `cpfId` (depository wins on conflict); no duplicates
- [x] 6.4 Filter to rows where `districtCodeSought == code or districtCodeHeld == code`
- [x] 6.5 Handle the no-candidates-found case (report + non-zero exit)
- [x] 6.6 Test merge dedup and district filtering with fixture feeds

## 7. Timeline context (race-summary)

- [x] 7.1 Fetch `filingSchedules/{year}` for `primaryElectionDate` and `generalElectionDate`
- [x] 7.2 Derive the as-of date from matched rows' `bankReportEndDate` (latest present); flag lagging rows
- [x] 7.3 Ensure money is presented as a single cumulative YTD figure (no primary/general split)

## 8. `ocpf race` command assembly (race-summary)

- [x] 8.1 Implement `commands/race.py`: `race(district, --year default current year, --json)`
- [x] 8.2 Wire resolution -> fetch/merge -> filter -> timeline -> render
- [x] 8.3 Default table: header (district, office, election dates, as-of) + columns (Candidate, Party, incumbent mark, Raised YTD, Spent YTD, Cash on Hand) with formatted currency
- [x] 8.4 `--json` output: merged/filtered records including `*Numeric` values, JSON-only on stdout
- [x] 8.5 End-to-end test/verification: `ocpf race "Suffolk and Middlesex" --year 2026` shows Brownsberger, Lander, and Wood with YTD figures

## 9. Docs and finish

- [x] 9.1 Update `README.md` with install (`uv`), usage, and the `ocpf race` example
- [x] 9.2 Add a `CLAUDE.md` note pointing to the OCPF endpoint reference and key data-model facts
- [x] 9.3 Run the full test suite and confirm the example command works against the live API
