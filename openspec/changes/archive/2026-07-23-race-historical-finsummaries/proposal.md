## Why

`ocpf race` shows candidates but no money for pre-2020 election years, because it
reads only the current-cycle feeds (`reports/legislative/depository/ytd/{year}`
and the non-depository race feed), which are near-empty before ~2020. The
historical money exists in the district-scoped
`onballot/finsummaries/{year}/{districtCode}` endpoint. Falling back to it makes
`ocpf race` work for older races (e.g. `ocpf race --year 2008 37th`).

## What Changes

- Add a fallback source for the `race` command: when the current-cycle feeds
  yield no candidate with money for the resolved district, fetch
  `onballot/finsummaries/{year}/{districtCode}` and use it instead. No hardcoded
  year cutoff — selection is driven by whether the current feeds have data.
- Normalize `finsummaries` rows into the shared candidate-row shape: parse the
  currency strings (`receipts`, `expenditures`, `endBalance`) into the numeric
  fields the renderer and sorter already use (`receiptsYtdNumeric`,
  `expendituresYtdNumeric`, `currentCashOnHandNumeric`), and carry through
  `isIncumbent` and `isWinner`.
- Render historical (final-totals) years with an adapted table: drop the
  *As of* line (there is no `bankReportEndDate`), relabel the money columns to
  final totals (`Raised` / `Spent` / `End Bal`), and add a `Won` column driven
  by `isWinner`. Incumbency comes from the `isIncumbent` flag rather than
  `districtCodeHeld` (which is `0` in this feed).
- `--json` for historical years emits the normalized records, including numeric
  money and `isWinner`.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `race-summary`: the command gains a historical data source and a final-totals
  rendering mode. The "YTD summary table" and "election timeline context"
  requirements gain scenarios for the historical/final-totals case (no as-of
  date, final-total column labels, winner marker, incumbency from the
  `isIncumbent` flag).

## Impact

- Code: `src/ocpf_cli/legislative.py` (add finsummaries fetch + normalization),
  `src/ocpf_cli/commands/race.py` (source-selection fallback, historical render
  path), possibly `src/ocpf_cli/render.py` (currency parsing helper if not
  already present).
- API: adds a dependency on the `onballot/finsummaries/{year}/{districtCode}`
  endpoint (read-only, unauthenticated, already public).
- Tests: new cases for the fallback trigger, currency-string normalization, and
  the historical render path (mocked API).
- No breaking changes to current-year behavior.
