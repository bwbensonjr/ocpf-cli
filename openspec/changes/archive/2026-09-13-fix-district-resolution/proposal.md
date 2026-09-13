## Why

A district that existed in an earlier redistricting cycle cannot be named, even
for a year in which it existed:

```
$ ocpf race "Worcester and Norfolk" --year 2020
error: "Worcester and Norfolk" matches no legislative (House/Senate) district
```

That was a real Senate district through the 2011 cycle, retired in the 2021 map.
Its 2020 candidates are in the feed; only the name cannot be resolved. The error
says the name is invalid, which is false — it was valid for twenty years.

`districts.py` resolves against the `districts` reference, and that reference is
**strictly the present map**: 365 rows, 200 legislative (160 House, 40 Senate,
Senate codes 105-170). Code 140 — Worcester & Norfolk — is not in it under any
office. There is no year-scoped fallback: `districts/{year}` returns `[]` and
`onballot/districts/{year}` is a 404.

## What Changes

- **Fold ordinal words to digits in `_normalize`.** The API always writes `1st`,
  `2nd`, `3rd`; other sources write `First`, `Second`, `Third`. `_normalize`
  already treats `&` and `and` alike, and this belongs in the same place. Cheap,
  self-contained, and independent of everything else here.
- **Resolve a retired district from the filer record that still names it.**
  `filer/{cpfId}` returns an `officeSought` object carrying **both the code and
  the era-correct description**, and it retains them for filers whose district no
  longer exists. Verified for the motivating case — Richard T. Moore, who left
  the Senate in 2014:

  ```json
  "officeSought": {"districtCode": 140, "officeDescription": "Senate",
                   "districtDescription": "Worcester & Norfolk",
                   "officeDistrict": "Senate, Worcester & Norfolk"}
  ```

  This is the discovery that makes the change tractable. The issue assumed the
  only handle on a retired district was scanning an office's whole code range and
  identifying the district by its candidates; the filer record names it outright.
- **Build a year-scoped district index** from the sources that carry era-correct
  names, in cost order:
  1. **2020 and later** — the depository YTD feed's `officeSought` string, which
     is era-correct and already fetched by `ocpf race`. No extra request. Feed
     coverage starts abruptly at 2020 (428 rows; 2019 has 13, 2018 has 2), which
     is why this tier stops there.
  2. **Earlier years** — `onballot/finsummaries/{year}/{code}` across the
     office's code range, which `race` already uses as its historical fallback.
     A 2010 Senate scan returns 39 populated codes out of 76 probed, each with
     `cpfId`s; resolving one `filer/{cpfId}` per populated code labels it with
     its era-correct name. Verified: code 140 in 2010 returns Moore (10315) and
     Roy (15242), and filer 10315 names the district.
- **Fail honestly when the name still cannot be placed.** A name that matches no
  district in the requested year SHALL say so in terms of that year rather than
  asserting the name is not a legislative district, and SHALL say when the name
  is known in other years.

Out of scope, deliberately:

- **Rewriting `ocpf race`'s data path.** This change is about turning a name into
  a code for a year; what `race` then does with the code is unchanged.
- **Non-legislative offices.** The `districts` reference covers sixteen other
  office types; legislative resolution is what `race` needs and what the issue
  reports.
- **A district's geographic identity across redistricting.** "Is the 2020 6th
  Bristol the same seat as the 2024 6th Bristol" is a question the API cannot
  answer and this change does not attempt. Names are resolved *within* a year.
- **Cross-filer report-log sweeps.** The report log carries era-correct district
  names back to 2002 and is a tempting fourth source, but it is the mechanism
  issue #3 needs and belongs with that change; the two tiers above cover the
  years `race` can actually report on.

## Capabilities

### Modified Capabilities
- `race-summary`: the **District resolution** requirement currently resolves a
  name against the current `districts` reference alone, with no notion of a
  year. It gains year-awareness — resolution is against the map as it stood in
  the requested year — plus ordinal folding and an error that distinguishes
  "no such district in that year" from "not a district name at all".

### New Capabilities

None. This changes how an existing requirement behaves rather than adding a
command surface.

## Impact

- **New code**: a year-scoped district index in `src/ocpf_cli/districts.py`
  (tiered as above) and the ordinal folding in `_normalize`.
- **Changed behavior**: `resolve_district` gains a year parameter. `commands/race.py`
  passes the year it already has. Names that resolve today continue to resolve to
  the same codes for current-map years — the new tiers are consulted only when
  the current map does not answer.
- **External API**: unchanged for 2020+ (the feed is already fetched). For an
  earlier year, a first resolution costs one probe per code in the office's range
  (76 for Senate, 164 for House) plus one `filer/{cpfId}` per populated code.
  That is a real cost and the reason the index is built lazily and only when the
  cheaper tiers miss.
- **Docs**: `CLAUDE.md` gains the verified facts — the `districts` reference is
  current-map only and omits retired codes entirely, `districts/{year}` returns
  `[]`, `onballot/districts/{year}` is a 404, depository feed coverage starts at
  2020, and `filer/{cpfId}.officeSought` carries an era-correct code and
  description.
- **No breaking changes** to output, though a previously failing invocation now
  succeeds.

## Related

Closes bwbensonjr/ocpf-cli#4. **Prerequisite for #3**: the special-election
roster groups report rows by `officeSought` strings like
`Senate Worcester & Norfolk`, and matching a user's `"Worcester and Norfolk"`
against those is exactly the normalization this change delivers. Doing #3 first
would mean writing that matching twice. Both changes carry deltas against
`race-summary`, so they must be sequenced rather than developed in parallel.
