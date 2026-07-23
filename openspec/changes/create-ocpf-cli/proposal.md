## Why

Answering a basic question about a Massachusetts race — "who is running in this
district and how much have they raised and spent?" — currently requires writing
throwaway Python against the OCPF API (`https://api.ocpf.us/`), knowing which of
its ~120 endpoints actually work, and knowing that the obvious ones
(`onballot/candidates`, `onballot/finsummaries`) are stale and return nothing for
current cycles. This change creates an opinionated command-line tool that turns
that recurring, multi-step lookup into a single command.

## What Changes

- Introduce a new Python CLI, `ocpf`, installed and run via `uv`, following the
  [clig.dev](https://clig.dev/) guidelines (human-readable default output,
  `--json` for machine use, clear errors, good `--help`).
- Add the primary command `ocpf race <district> [--year <year>]`, which:
  - Resolves a district by name (substring/fuzzy match against the API's own
    `districts` reference) or accepts a raw district code, and disambiguates
    near-collisions (e.g. `Suffolk and Middlesex` #166 vs `Middlesex & Suffolk`
    #151).
  - Fetches the legislative (House/Senate) year-to-date field from
    `reports/legislative/depository/ytd/{year}` and the non-depository feed, and
    **merges them on `cpfId`** so the whole field is captured.
  - Filters candidates to the target district (`districtCodeSought` or
    `districtCodeHeld`).
  - Renders a YTD summary table: candidate, party, incumbent mark, receipts YTD,
    expenditures YTD, cash on hand.
  - Presents primary vs. general as **timeline context, not a money filter** —
    the header shows the primary/general election dates (from
    `filingSchedules/{year}`) and the as-of reporting period/date (from each
    row's `bankReportEndDate`); the money is the single cumulative YTD figure the
    API provides, never split per election.
- Add a shared HTTP client for the OCPF API and shared output rendering
  (table + `--json`) that later commands can reuse.
- Establish the project scaffolding: `pyproject.toml` (uv), package layout,
  entry point, and tests.

Out of scope for this change (deliberate, to keep v1 focused):
- Office types other than legislative (statewide, county, mayoral, ballot
  question) — the endpoint-routing table is designed to extend to these later.
- Drill-down into individual reports, donors, or expenditures
  (`report/{id}`, `search/items`) — v1 stops at the YTD summary table.
- Free-text candidate-name search (the API's filer name-search endpoints are
  broken; resolution is district-first).

## Capabilities

### New Capabilities
- `cli-foundation`: The `ocpf` command entry point, an OCPF API HTTP client
  (base URL, GET-JSON, timeouts, error handling), and shared output rendering
  (human table default, `--json`), plus global conventions (exit codes,
  error messages) per clig.dev.
- `race-summary`: The `ocpf race` command — district resolution, legislative
  YTD fetch and depository/non-depository merge, district filtering, and the
  timeline-aware YTD summary table.

### Modified Capabilities
<!-- None — this is a greenfield project with no existing specs. -->

## Impact

- **New codebase**: greenfield Python package (no existing code to modify).
- **Dependencies**: `uv` for packaging; a CLI framework (Typer/Click) and an
  HTTP client (`requests` or `httpx`) — finalized in design.
- **External API**: read-only, unauthenticated GET requests to
  `https://api.ocpf.us/`. Behavior is constrained by that API's coverage and
  quirks (documented in `ocpf-analysis/api/ENDPOINT-STATUS.md`).
- **No breaking changes** (nothing exists yet).
