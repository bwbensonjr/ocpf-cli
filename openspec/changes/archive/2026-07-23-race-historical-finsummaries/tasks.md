## 1. Currency parsing

- [x] 1.1 Add a `parse_currency` helper in `render.py` (inverse of
  `format_currency`): strip `$` and commas, parse to float, treat blank/`"$0.00"`
  and unparseable input as `0.0`.
- [x] 1.2 Add unit tests for `parse_currency` covering `"$63,727.50"`, `"$0.00"`,
  empty string, and a malformed value.

## 2. Historical data source in `legislative.py`

- [x] 2.1 Add `FINSUMMARIES_PATH = "onballot/finsummaries/{year}/{code}"` and a
  `fetch_finsummaries(year, code)` that calls `api.get_json` and returns the raw
  list.
- [x] 2.2 Add `normalize_finsummaries(rows)` that maps each row to the shared
  candidate-row shape: `filerName`, `partyAffiliation`, `receiptsYtdNumeric`,
  `expendituresYtdNumeric`, `currentCashOnHandNumeric` (from `endBalance`, all via
  `parse_currency`), plus `isIncumbent` and `isWinner`.
- [x] 2.3 Add a helper to detect whether a set of matched rows has any money
  (any nonzero numeric receipts/expenditures/cash), for the fallback trigger.
- [x] 2.4 Add unit tests for `normalize_finsummaries` (currency→numeric mapping,
  flags carried through) and the has-money helper.

## 3. Source selection + historical render in `race.py`

- [x] 3.1 After `fetch_merged_field` + `filter_by_district`, if the matches have
  no money, fetch + normalize `finsummaries` for the resolved code and mark the
  result as historical; if that is also empty, keep the existing "no candidates
  found" error path.
- [x] 3.2 Update `_is_incumbent` usage so historical rows use the `isIncumbent`
  flag instead of `districtCodeHeld == code`.
- [x] 3.3 Extend `_render_table` (or add a historical branch) to: omit the as-of
  line when there is no as-of date, relabel money columns to `Raised` / `Spent` /
  `End Bal` in historical mode, and add a `Won` column driven by `isWinner`.
- [x] 3.4 Ensure `build_timeline` degrades cleanly for historical data (no
  `bankReportEndDate` → `as_of_date` None, `lagging_filers` empty).
- [x] 3.5 Ensure `--json` emits the normalized historical records including
  `isWinner`.

## 4. Tests and verification

- [x] 4.1 Add a mocked test: current feeds empty for a district/year → falls back
  to `finsummaries` and renders the historical table with money and winner
  marker.
- [x] 4.2 Add a mocked test: current feeds have money → `finsummaries` is not
  called and current-year output is unchanged.
- [x] 4.3 Add a mocked test: neither source has candidates → non-zero exit with
  the "no candidates found" message.
- [x] 4.4 Run `uv run pytest` and confirm all tests pass.
- [x] 4.5 Smoke-test against the live API: `uv run ocpf race --year 2008 37th`
  shows Benson/Hayes with money and a winner marker.
