## Why

Year-aware district resolution (PR #7) promised that a district retired at
redistricting stays reachable for the years it existed. It does not hold for
pre-2020 **odd** years, which is exactly when special elections happen:

```
$ ocpf race "2nd Hampden and Hampshire" --year 2013 --special
Searching Senate districts for 2013...
Searching House districts for 2013...
error: "2nd Hampden and Hampshire" was not a legislative district in 2013; it
existed in 2020 as Senate, 2nd Hampden & Hampshire (code 114)
```

It *was* a district in 2013. Bartley (12646) and Humason (13888) contested a
special for it that September, and `reports/log` returns their filings under
`officeSought` "Senate 2nd Hampden & Hampshire". The failure is upstream of the
special-election path added in #8 — the roster code never runs.

The cause is that resolution has no tier with data for these years. Tier 2 (the
legislative feed) starts at 2020. Tier 3 sweeps
`onballot/finsummaries/{year}/{code}`, which returns **zero rows for 2007, 2013,
2015, 2017, 2019 and for 2020 onward**, measured across Senate codes 105-145
rather than sampled. A pre-2020 odd year falls between them. Worse, the failure
costs the full ~20-30 second code-range sweep before reporting nothing.

Tracked as issue #9.

## What Changes

- **Add a fourth resolution tier sourced from the special-election report-log
  sweep.** The sweep added in #8 already carries era-correct `officeSought`
  strings paired with the year of each filing, and it is memoized, so a lookup
  costs nothing once `--special` has fetched it. Grouping its rows by office and
  year names the districts that held a special in the requested year.
- **Recover the district code from the filers the sweep already identifies.**
  Sweep rows carry no district code, but they carry cpfIds, and
  `filer/{cpfId}.officeSought` reports a `districtCode` with a
  `districtDescription`. Tallying across a seat's filers and keeping only those
  whose description still matches the seat recovers the code — verified to
  recover **3 of the 4** failing seat-years: code 114 for Senate 2nd Hampden &
  Hampshire 2013, 128 for 2nd Plymouth & Bristol 2015, 148 for 1st Suffolk &
  Middlesex 2007.
- **Make `District.code` optional, so a district known by name but not by code
  still resolves.** `filer/{cpfId}` reports each filer's **most recent** office,
  not the one they sought in the requested year, so a roster whose filers have
  all moved on yields no code. This is real: Senate 1st Hampden & Hampshire 2013
  has one filer in the sweep, Franco (14025), who now reports Governor's Council.
  That race becomes reachable with its code omitted rather than unreachable.
  **BREAKING** for consumers of the `--json` `districtCode` field, which becomes
  nullable, and for any code treating `District.code` as a guaranteed `int`.
- **Stop asserting a district did not exist when the sweep says it did.** The
  error for an unresolvable name keeps its year-relative wording, but a name the
  sweep knows for that year no longer reaches it.

Out of scope, deliberately:

- **Recovering codes for districts that held no special election.** The new tier
  is seeded from the special-election sweep, so it names only seats that appear
  there. A renamed district in a pre-2020 odd year that held no special stays
  unresolvable — and has nothing to report anyway, since odd years hold no
  regular contest.
- **Fixing `onballot/finsummaries`.** Its odd-year gap is OCPF's, not ours. Tier
  3 stays as it is for the even years where it works.
- **A general cross-filer district index.** Sweeping every report type to build a
  full historical district map is a much larger change with a much larger request
  cost, and nothing currently needs it.
- **The ambiguity case.** `"Plymouth and Norfolk"` for 2016 matches both 1st and
  2nd Plymouth and Norfolk in the current map and is reported as ambiguous. That
  is resolution behaving correctly on an under-specified name, not this gap.

## Capabilities

### Modified Capabilities

- `race-summary`: the "District resolution" requirement gains the report-log
  tier and the optional-code case. Its existing guarantees are unchanged —
  current-map resolution still short-circuits, ambiguity is still never guessed,
  and failure is still reported in terms of the requested year. The
  "`ocpf race` command" and JSON-output requirements gain the nullable district
  code.

### New Capabilities

None. This is behavior of district resolution, which the project specs under
`race-summary` alongside the command that uses it.

## Impact

- **New code**: a report-log-backed tier in `src/ocpf_cli/districts.py`, reusing
  `reports.fetch_special_reports` and the filer-tally technique
  `_district_for_code` already uses.
- **Changed types**: `District.code` becomes `int | None`. Every read of it —
  the race header, the special-election header and `--json`, `filter_by_district`
  — needs a None path. `filter_by_district` is the one to watch: a None code must
  match nothing rather than matching rows whose code is missing.
- **External API**: no new endpoint. One `filer/{cpfId}` lookup per candidate on
  the seat, bounded by roster size (two to eight), and only on the tier-4 path.
- **Cost**: the new tier runs before tier 3's code-range sweep, so the affected
  lookups get *faster* — the ~20-30 second sweep is skipped when the log answers.
- **Docs**: `CLAUDE.md` records that `filer/{cpfId}.officeSought` is
  most-recent-office rather than era-correct, which is the fact that makes the
  tally necessary and the residual case unavoidable.

## Related

Closes bwbensonjr/ocpf-cli#9. Builds on the sweep from #8 and the year-aware
resolution from #7. The `CLAUDE.md` coverage note corrected in `aa59263` records
the odd-year gap that motivates this.
