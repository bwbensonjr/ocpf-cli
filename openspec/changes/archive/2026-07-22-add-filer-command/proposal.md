## Why

The `ocpf race` command answers "who is running in this district?" and returns a
row per candidate — including each candidate's `cpfId` — but there is no way to
pivot from that list to a single candidate's full filing picture: their committee
profile, cumulative year-to-date finances, and the reports they have actually
filed (and when). Answering "what has this specific candidate filed, and what do
their finances look like?" still means hand-writing Python against
`filer/payload/{cpfId}`. This change adds the natural companion command to
`race`: `ocpf filer`.

## What Changes

- Add the command `ocpf filer <filer> [--year <year>] [--json]`, which produces
  a single candidate/committee filing summary:
  - **Profile** — committee name, candidate name, party, office sought/held,
    active/closed status, organization date, and treasurer, from
    `filer/{cpfId}` (delivered inside `filer/payload/{cpfId}`).
  - **Year-to-date finances** — cumulative receipts, expenditures, and cash on
    hand from the payload's `ytdReport` (the same honest cumulative figure the
    `race` table shows, never split by election).
  - **Recent filing log** — the most recent reports from the payload's
    `logReports`: report type, reporting period, date filed, receipt and
    expenditure totals, and a link to each report on ocpf.us.
- Accept the `<filer>` argument as **either** a raw numeric `cpfId` (works for
  any filer type) **or** a candidate name matched against the legislative field
  for the year (reusing the `race` merge), with the same no-guess ambiguity
  handling as district resolution: zero matches → error, one → proceed, many →
  print the candidates with their cpfIds and exit.
- Reuse the existing `cli-foundation` seam: the shared API client, table/JSON
  rendering, stderr status routing, and exit-code conventions. `--json` emits
  the underlying filer/YTD/report records including numeric values.

Out of scope for this change (deliberate, to keep v1 focused):
- Drilling into an individual report's line items — donors, individual
  expenditures, subvendor payments (`report/{id}`, `search/items`).
- Name resolution for non-legislative filers (statewide, county, mayoral, PAC,
  ballot-question). Their data is fully reachable **by cpfId**; only name
  lookup is legislative-only in v1, mirroring the project's legislative scope.
- Audit issues and correspondence (`filer/issues/...`,
  `filer/correspondence/...`).
- Full paginated report history (`reports/reportList/{cpfId}`) — v1 shows the
  recent log the payload already returns.

## Capabilities

### New Capabilities
- `filer-lookup`: The `ocpf filer` command — filer resolution (numeric cpfId or
  legislative name match), the single-call `filer/payload/{cpfId}` fetch, and
  the rendered profile + YTD finances + recent filing log (human default and
  `--json`).

### Modified Capabilities
<!-- None — this reuses cli-foundation without changing its requirements. -->

## Impact

- **New code**: `src/ocpf_cli/commands/filer.py`; a new `filer` subcommand
  registered in `cli.py`. Name resolution reuses the merge helpers in
  `commands/race.py` (may be factored into a shared module if cleaner).
- **Reused foundation**: `api.get_json` / `OcpfApiError`, `render` (table, JSON,
  currency, stderr status), and the existing exit-code conventions — no changes
  to their requirements.
- **External API**: read-only GET requests to `filer/payload/{cpfId}` (one call
  per lookup) and, for name resolution, the legislative YTD feeds already used
  by `race`.
- **No breaking changes**: purely additive; `ocpf race` is unaffected.
