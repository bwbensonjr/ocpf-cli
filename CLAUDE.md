# CLAUDE.md

Guidance for working in this repository.

## What this is

`ocpf` is a Python CLI (managed with `uv`, built on Typer + httpx) over the
OCPF API at `https://api.ocpf.us/` — a read-only, unauthenticated JSON API.

## Layout

```
src/ocpf_cli/
  cli.py            # Typer app; a callback keeps it in multi-command mode
  api.py            # get_json(path, params) + OcpfApiError + BASE_URL
  render.py         # table rendering, JSON emission, currency formatting
  districts.py      # district name/code -> code resolution
  commands/race.py  # `ocpf race` — fetch/merge/filter/timeline/render
tests/              # pytest; API and feeds mocked (respx / monkeypatch)
```

## OCPF API reference and data-model facts

The endpoint landscape is mapped in
`../ocpf-analysis/api/ENDPOINT-STATUS.md` (available locally). Key facts that
drove this design:

- The obvious "candidates in a district" endpoints —
  `onballot/candidates/{year}/{code}` and `onballot/finsummaries/...` — are
  **stale** (data stops ~2012) and return empty for current cycles. Do not use
  them for current races.
- The working source of the current legislative field with YTD money is
  `reports/legislative/depository/ytd/{year}`, which returns
  `{ reports: [...], summary: {...} }`. Each report row carries `cpfId`,
  `filerName`, `partyAffiliation`, `districtCodeSought`, `districtCodeHeld`,
  `officeSought`, `receiptsYtd(+Numeric)`, `expendituresYtd(+Numeric)`,
  `currentCashOnHand(+Numeric)`, `startBalance(+Numeric)`, and
  `bankReportEndDate` (format `M/D/YYYY`).
- The non-depository feed is `reports/legislative/race/nd/{year}` and returns a
  **bare list** (not `{reports}`). It is often empty. Merge it with the
  depository feed by `cpfId`, depository winning on conflict.
- `districtCodeHeld == -1` marks a non-incumbent; an incumbent's
  `districtCodeHeld` equals the district code.
- `districts` returns 365 rows of `{office, code, description, ...}`. Filter to
  `office in {"House", "Senate"}` for legislative resolution.
- `filingSchedules/{year}` provides `primaryElectionDate` and
  `generalElectionDate` (timeline context only — money is never split by
  election).
- Free-text filer name-search endpoints are dead (404). Resolution is
  district-first.

## Conventions

- Data to stdout; human status/progress and errors to stderr (clig.dev).
- Non-zero exit on failure (bad input, API error, no matches); zero on success.
- All HTTP goes through `api.get_json`; commands raise/catch `OcpfApiError`.
- Double-quoted strings per project style.

## Common commands

```bash
uv sync --extra dev      # install deps + test tooling
uv run pytest            # run tests
uv run ocpf race "..."   # run the CLI from source
```

## Releasing

Notable changes are recorded in [CHANGELOG.md](CHANGELOG.md).

Releases are published to PyPI automatically by GitHub Actions when a version tag
is pushed. Versioning is tag-driven (via `hatch-vcs`), so the tag is the single
source of truth for the package version:

```bash
git tag v0.1.0
git push --tags
```
