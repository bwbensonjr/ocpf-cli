## Why

Year-aware district resolution promised that a district retired at redistricting
stays reachable for the years it existed. For even years it still does not hold
whenever the seat's former candidates have all moved on:

```
$ ocpf race "1st Plymouth and Bristol" --year 2014
Searching Senate districts for 2014...
Searching House districts for 2014...
error: "1st Plymouth and Bristol" was not a legislative district in 2014; it
existed in 2020 as Senate, 1st Plymouth & Bristol (code 104)
```

It *was* a district in 2014, and the roster is sitting right there:
`onballot/finsummaries/2014/104` returns Pacheco (11448) and Rosa (15700).

The cause is a gap in tier 4, the `finsummaries` code-range sweep. That tier
knows a candidate code with certainty — it came from the URL it just fetched a
populated roster from — but it can only *name* that code by asking each filer
what office they sought, via `filer/{cpfId}.officeSought`. That field reports a
filer's **most recent** office, not the one they sought in the requested year.
`_district_for_code` correctly discards every filer whose reported code no longer
matches the seat (without that guard, Brady and Diehl — who both now report 169 —
would mislabel district 128). But when the discard removes *every* filer, the
tally is empty and the function returns `None`. A code that is known becomes a
district that "did not exist".

Senate 104, retired at the 2021 redistricting when Pacheco's seat became code 170
(`3rd Bristol and Plymouth`), shows the whole pattern:

| year | roster, and the code each filer reports today | result |
|------|----------------------------------------------|--------|
| 2010 | Pacheco→170, Pottier→104, Saade→104 | resolves (2 votes) |
| 2011 | Pacheco→170, Pottier→104 | resolves (1 vote) |
| 2012 | Pacheco→170 | **fails** |
| 2014 | Pacheco→170, Rosa→157 | **fails** |
| 2016 | Pacheco→170, Wright→412 | **fails** |
| 2018 | Pacheco→170 | **fails** |

Resolution succeeds only by the accident that Pottier never ran again. The seat
is unreachable for four of the six years it is populated, and each failure costs
the full code-range sweep before reporting nothing.

This is the same class of problem the report-log tier already solved for odd
years, and it has the same answer — filings know what a seat was called when it
was filed for — but arriving from the opposite direction: there the code was
missing, here the name is.

## What Changes

- **Name a swept district code from the era-correct office strings on its
  filers' reports, when the filer tally comes up empty.** `reports/log?CpfId=`
  returns a filer's reports each carrying an `officeSought` string as it stood at
  filing time. For cpfId 11448 that is 331 rows: 172 reading
  `Senate 1st Plymouth & Bristol` and 159 reading `Senate 3rd Bristol and
  Plymouth`, separable by the reporting period `reports.py` already parses. Taking
  the office string from the rows whose period falls in the requested year names
  the seat for that year without depending on whether the filer ever ran again.
- **Keep the existing filer tally as the primary path.** It is one request per
  filer against an endpoint already in use, it answers whenever any filer stayed
  put, and its most-reported-label rule is what keeps a code from being mislabeled
  by a filer who moved. The new source runs only when that tally yields nothing,
  so no lookup that succeeds today gets slower or changes its answer.
- **Report a swept code whose name cannot be established as unnamed rather than
  as absent.** A populated roster at a code is proof the district existed that
  year. Where neither source names it, the sweep SHALL NOT claim the district did
  not exist; it simply cannot match it against a requested name.

Out of scope, deliberately:

- **Changing the filer-tally discard rule.** The `districtCode != code` filter is
  load-bearing and stays exactly as it is.
- **Reading money, amendment state, or any other field from log rows.** The log
  returns every amendment generation of a filing, so its totals identify a version
  rather than a candidate. Only the office string and the reporting period are
  wanted here; money continues to come from `finsummaries`.
- **Making the log tier the primary namer, or pre-building a historical district
  index.** Sweeping every filer's log to construct a full year-by-year district
  map is a much larger change with a much larger request cost, and the lazy
  fallback answers the cases that are broken.
- **Odd years and years `finsummaries` does not cover.** Tier 4 only runs for
  years `finsummaries` covers; the existing special-election log tier continues to
  own the rest.
- **`onballot/finsummaries`' own coverage gaps.** Those are OCPF's.

## Capabilities

### New Capabilities

None. This is behavior of district resolution, which the project specs under
`race-summary` alongside the command that uses it.

### Modified Capabilities

- `race-summary`: the "District resolution" requirement gains the case where a
  district code is established for the year but its name must come from the
  filings rather than from the filers' current office. Its existing guarantees are
  unchanged — current-map resolution still short-circuits, ambiguity is still
  never guessed, a code is still never borrowed from a different year, and failure
  is still reported in terms of the requested year.

## Impact

- **New code**: an era-correct naming helper in `src/ocpf_cli/reports.py`
  (log rows filtered by cpfId and year, reduced to office strings), called from
  `_district_for_code` in `src/ocpf_cli/districts.py` as a fallback.
- **External API**: no new endpoint. One `reports/log?CpfId=` request per filer,
  incurred only for codes whose filer tally came up empty, and only on the tier-4
  path. Paging follows the 1-based `StartIndex` rule and the bare-list
  termination signal already implemented in `reports.py`; `reports/log` filters
  fail closed, so a mistyped filter yields an empty answer rather than the
  unfiltered database.
- **Unchanged**: `_normalize` needs no change — it already folds `&`/`and` and
  ordinal words, which is why the reported name matches the requested one once it
  is found. `District.code` is already `int | None`; nothing about the optional
  code changes here.
- **Performance**: strictly additive on the failing path and neutral elsewhere.
  Codes that resolve today make no extra request; codes that fail today trade a
  wrong answer for a few more.
- **Docs**: `CLAUDE.md` gains the fact that `reports/log?CpfId=` carries an
  era-correct `officeSought` usable to name a district code, complementing the
  existing note that `filer/{cpfId}.officeSought` is most-recent-office.

## Related

Follows the sweep-floor fix in the same branch, which widened
`OFFICE_CODE_RANGES["Senate"]` from `range(105, 181)` to `range(104, 181)` so the
sweep reaches code 104 at all. That fix made 2010 and 2011 work and is what
exposed this defect for 2012, 2014, 2016 and 2018. Builds on the report-log tier
and the optional `District.code` from `resolve-districts-from-report-log`.
