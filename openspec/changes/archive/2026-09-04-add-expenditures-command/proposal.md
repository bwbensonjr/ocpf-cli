## Why

`ocpf race` answers "who is running?" and `ocpf filer` answers "what has this
committee filed, and what are their totals?" — but both stop at aggregates. The
question that actually gets asked of campaign-finance data is "who did this
committee **pay**, and how much?" Answering it today means hand-writing HTTP
against an endpoint that is undocumented in the project's own notes: a real
session had to brute-force the `SearchTypeCategory` parameter one letter at a
time to discover that expenditures live behind `B`, then paginate and grep the
JSON locally, just to establish that a committee had made no payments to a named
consultant. The `add-filer-command` proposal deliberately deferred report line
items to a later change; this is that change.

The endpoint is better-documented than the project believed. OCPF publishes a
full OpenAPI spec at `https://api.ocpf.us/swagger/v1/swagger.json` that
enumerates every `search/items` parameter. This change captures that knowledge in
code and in the repo's API reference so nobody rediscovers it by brute force.

## What Changes

- Add the command
  `ocpf expenditures <filer> [--year <year>] [--since <date>] [--until <date>] [--vendor <text>] [--min-amount <n>] [--max-amount <n>] [--by-vendor] [--limit <n>] [--json]`,
  which lists the payments a single committee has made:
  - **Itemized view** (default) — one row per expenditure: date, amount, vendor,
    purpose, and the record type (which distinguishes a committee-reported
    expenditure from a bank-reported one), followed by a total and record count.
  - **Rollup view** (`--by-vendor`) — totals and counts grouped by payee, largest
    first, computed client-side from the same fetched records.
  - **Provenance** — each record carries the OCPF report it came from, so a
    finding can be traced back to a filing.
- Reuse `ocpf filer`'s existing filer resolution (numeric `cpfId`, or a
  legislative name matched for the year) so `ocpf expenditures Uyterhoeven`
  works the same way `ocpf filer Uyterhoeven` does. Resolution logic moves out of
  `commands/filer.py` into a shared module rather than being imported across
  command modules or duplicated.
- Fetch from `search/items` with `SearchTypeCategory=B`, paginating on
  `StartIndex`/`PageSize` until the record count reported by `withSummary=true`
  is satisfied, so a result set is never silently truncated.
- Report a **filtered search that matches nothing as a success** (exit 0) with an
  explicit "no matching expenditures" line naming what was searched. A vendor
  filter returning zero is a finding, not a failure. An unresolvable filer, an
  API error, or a filer with no expenditure records at all remains non-zero.
- Record the `search/items` contract — the `SearchTypeCategory` codes, the
  silent-fallback hazard, the working `Name` filter and the inert `VendorName`
  one, and the swagger URL — in the project's OCPF API reference notes
  (`CLAUDE.md`), so the next command that needs item search starts from
  documentation instead of probing.

Out of scope for this change (deliberate, to keep v1 focused):
- Receipt and contribution search (`SearchTypeCategory=R`) and subvendor
  payments (`S`). The fetch layer is written so both are a small follow-up, but
  each deserves its own command surface and its own spec.
- Cross-filer vendor search ("every committee that paid this firm"), which is
  the same endpoint without a `CpfId` but a different question and a much larger
  result set.
- Resolving the payee behind opaque bank-reported entries such as
  `OUTGOING WIRE TRANSFER`. The API does not carry it; only the filed report
  images do. The command SHALL surface these plainly rather than imply the payee
  list is complete.
- Non-legislative name resolution, unchanged from `ocpf filer`: any filer is
  reachable by `cpfId`, only name lookup is legislative-only.

## Capabilities

### New Capabilities
- `expenditure-search`: The `ocpf expenditures` command — paginated retrieval of
  a filer's expenditure records from `search/items`, the date/vendor/amount
  filters, the itemized and `--by-vendor` rendered views, the empty-result
  contract, and `--json`.

### Modified Capabilities
- `cli-foundation`: The "Errors and exit codes" requirement currently makes "no
  matching data" a non-zero exit unconditionally. It gains a carve-out: when a
  command applies a user-supplied *filter* to a successfully retrieved result
  set and the filter matches nothing, that is a successful empty result (exit
  zero) reported on standard output, not an error. Failure to retrieve, resolve,
  or parse is unchanged.
`filer-lookup` is **not** modified. `ocpf expenditures` depends on its
filer-resolution contract and the implementation shares that code, but no
requirement of the `ocpf filer` command changes, so it gets no delta.

## Impact

- **New code**: `src/ocpf_cli/commands/expenditures.py`; an `expenditures`
  subcommand registered in `cli.py`; a new `search.py` (or equivalent) holding
  the paginated `search/items` client.
- **Refactor**: filer resolution (`resolve_filer`, `FilerMatch`,
  `FilerResolutionError`) moves from `commands/filer.py` to a shared module,
  imported by both commands. `commands/filer.py` behavior is unchanged — this is
  a pure move, and its existing tests must pass untouched.
- **Reused foundation**: `api.get_json` / `OcpfApiError`, `render` (table, JSON,
  currency, stderr status). `render` may gain a right-aligned-currency-column
  helper if the existing table renderer does not already cover the rollup view.
- **External API**: read-only GET requests to `search/items`. One request per
  page of 500–1000 records; a large committee is a handful of calls. A
  ~1,000-record committee spanning six years is roughly 1–2 requests.
- **Docs**: `CLAUDE.md` gains the `search/items` facts above;
  `../ocpf-analysis/api/ENDPOINT-STATUS.md` is the sibling repo's file and is
  **not** edited by this change, though it is the reason the knowledge was
  missing.
- **No breaking changes**: purely additive. The `cli-foundation` exit-code
  refinement narrows when non-zero is returned for a case no existing command
  currently produces — `race` and `filer` treat an empty result as unresolvable
  input, which stays non-zero.
