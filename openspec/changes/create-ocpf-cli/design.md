## Context

This is a greenfield Python CLI over the OCPF REST API
(`https://api.ocpf.us/`), a read-only, unauthenticated JSON API. The endpoint
landscape was previously mapped in `ocpf-analysis/api/ENDPOINT-STATUS.md` (94 of
118 endpoints working) and re-verified live during exploration for this change.

Key findings that constrain the design:

- The endpoints that *look* like the front door for "candidates in a district for
  an election" — `onballot/candidates/{year}/{code}` and
  `onballot/finsummaries/{year}/{code}` — are **stale**: their data stops around
  2012 and they return empty for current cycles.
- The working source of the current legislative field with YTD money is the
  report-page family: `reports/legislative/depository/ytd/{year}` returns
  `{ reports: [...], summary: {...} }`, where each report row carries `cpfId`,
  `filerName`, `partyAffiliation`, `districtCodeSought`, `districtCodeHeld`,
  `officeSought`, `receiptsYtd(+Numeric)`, `expendituresYtd(+Numeric)`,
  `currentCashOnHand(+Numeric)`, `startBalance(+Numeric)`, and `bankReportEndDate`.
  A single call returns the whole legislative field (~hundreds of rows) for the
  year, filterable by district code. A parallel non-depository feed exists for
  smaller filers.
- Free-text filer name-search endpoints (`filers/listings/...`,
  `filers/options/...`, `public/search/...`) are dead (404). Resolution must be
  **district-first**, keyed off the working `districts` reference.
- `filingSchedules/{year}` returns `primaryElectionDate`, `generalElectionDate`,
  and a `legislativeSchedule` of reporting periods — the source of timeline
  context.
- YTD money is a single cumulative figure per candidate (as of their latest filed
  report); the API does not segment it by primary vs. general.

## Goals / Non-Goals

**Goals:**
- One command, `ocpf race <district> [--year]`, that answers "who is running in
  this legislative district and what are their YTD finances?" in a single call
  chain.
- District-first resolution using the API as the point of truth.
- Honest presentation: cumulative YTD money with election dates and an as-of date
  as timeline context.
- A small, reusable foundation (API client, table/JSON rendering) that future
  commands (`ocpf filer`, `ocpf report`, other office types) can build on.

**Non-Goals:**
- Non-legislative office types (statewide, county, mayoral, ballot question).
  The endpoint-routing seam is designed so these slot in later.
- Drill-down into reports, donors, or expenditures.
- Free-text candidate name search (unsupported by the API).
- Local caching or a bundled dataset — every run reads live from the API.
- Writing to OCPF (the API is read-only anyway).

## Decisions

### CLI framework: Typer
Use Typer (built on Click). It gives clean noun/verb subcommands, typed options,
and good auto-generated `--help` with minimal boilerplate, and a `--json` flag is
trivial to add per command. *Alternatives:* raw `argparse` (more boilerplate, no
typed options); Click directly (Typer is a thinner path to the same result).

### HTTP client: `httpx` (or `requests`)
A thin wrapper module exposes `get_json(path, params=None)` against the fixed base
URL with a timeout, returning parsed JSON and raising a typed `OcpfApiError` on
failure. The existing analysis scripts use `requests`; either is fine. Prefer
`httpx` for timeouts/typing ergonomics, but this is a low-stakes choice the
implementer may settle. *Rationale:* isolating all HTTP in one module keeps
commands testable (mock one function) and centralizes error handling.

### Package layout
```
src/ocpf_cli/
  __init__.py
  cli.py            # Typer app, wires subcommands, global options
  api.py            # OCPF client: get_json(), OcpfApiError, BASE_URL
  render.py         # table rendering + JSON emission helpers
  districts.py      # district resolution (name/code -> code) via `districts`
  commands/
    race.py         # `ocpf race` command
tests/
pyproject.toml      # uv project, console_script entry point `ocpf`
```
Keep string literals double-quoted per project convention.

### District resolution
Fetch `districts` (365 rows). If `<district>` parses as an int and matches a
legislative code, use it. Otherwise case-insensitively substring-match the value
against `description` among House/Senate offices. Exactly one match → proceed;
zero → error; more than one → print the candidates (code, office, description) and
exit without guessing. Normalize `&`/`and` and surrounding whitespace so
`"Suffolk and Middlesex"` matches cleanly while staying distinct from
`"Middlesex & Suffolk"`.

### Field fetch and merge
Fetch both `reports/legislative/depository/ytd/{year}` and the non-depository
legislative feed for the year; take `.reports`; merge into a dict keyed by
`cpfId` (depository wins on conflict, since bank reports are the fuller record);
then filter to rows where `districtCodeSought == code or districtCodeHeld == code`.
*Rationale:* small/inactive candidates file non-depository, so a single feed can
miss part of the field.

### Timeline context
Fetch `filingSchedules/{year}` once for `primaryElectionDate` and
`generalElectionDate`. Derive the as-of date from the matched rows'
`bankReportEndDate` (show the latest present; footnote any row that lags). Render
these in the table header. Never divide money by election.

### Output contract
Default: a header block (district, office, election dates, as-of) plus an aligned
table (Candidate, Party, incumbent mark, Raised YTD, Spent YTD, Cash on Hand).
`--json`: emit the merged/filtered records including the `*Numeric` values.
Human status/progress (if any) goes to stderr so stdout stays pipeable.

## Risks / Trade-offs

- **API coverage/quirks** → The tool is only as complete as the legislative YTD
  feeds. Mitigation: merge depository + non-depository; if a known candidate is
  absent, that reflects unfiled reports, not a tool bug — keep the as-of date
  visible so users read the figures in context.
- **Endpoint drift / outages** (OCPF changes routes or returns 5xx) → Typed
  `OcpfApiError` with a clear message and non-zero exit; do not crash with a raw
  stack trace.
- **Mixed as-of dates across candidates** → Header shows the latest date; lagging
  rows are footnoted so comparisons aren't silently apples-to-oranges.
- **District name ambiguity** → Never guess; print matches and let the user pick a
  code. Trade-off: a bit more friction for a lot more trust.
- **Legislative-only v1** → Requesting a statewide/county/mayoral district yields
  no legislative match and a clear "no match" error. Acceptable for v1; the
  office-type routing seam makes expansion additive.

## Open Questions

- `httpx` vs `requests` — implementer's choice; both satisfy the client contract.
- Exact rendering library for tables (hand-rolled alignment vs. `rich`) — keep it
  simple; `rich` is optional polish, not required by the spec.
- Whether to expose an `--office house|senate` narrowing flag to further
  disambiguate names, or rely solely on printing matches. Default: rely on
  printing matches for v1; add the flag only if disambiguation proves noisy.
