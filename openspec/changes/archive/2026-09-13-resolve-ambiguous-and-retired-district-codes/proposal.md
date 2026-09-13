## Why

A retired district whose name is a prefix of two current ones cannot be reached
by name, because the name is ambiguous, and cannot be reached by code either,
because the code is rejected. There is no way to ask the question.

`Plymouth and Norfolk` was a Senate seat through the 2011 cycle; the 2021 map
split it into `1st Plymouth and Norfolk` (167) and `2nd Plymouth and Norfolk`
(169). It is a real seat with real contests — Hedlund, O'Connor, a 2016 special:

```
$ ocpf race "Plymouth and Norfolk" --year 2016
error: "Plymouth and Norfolk" matches more than one legislative district
  Senate, 2nd Plymouth and Norfolk (code 169)
  Senate, 1st Plymouth and Norfolk (code 167)
```

Both suggestions are dead ends for the requested year — neither district existed
in 2016 — so the ambiguity is being resolved against the **present map** while
the query names a year, and the one district that did exist is not among the
options.

Two separate defects produce this, and each is independently reachable:

**1. A current-map ambiguity short-circuits every year-aware tier.**
`resolve_district` raises on a tier-1 ambiguity before tier 2, 3 or 4 is ever
consulted, so the year the caller asked about is never used. The data to answer
is already in hand or one tier away: the 2020 legislative feed carries exactly
one district matching this name — code 127, `Plymouth & Norfolk` — and for 2016
the `finsummaries` sweep names code 127 `Plymouth & Norfolk` too. Measured on the
2020 feed, the name has **one** exact match and **one** substring match; the
present map is the only source where it has two.

**2. A numeric code is validated only against the present map and
`finsummaries`.** Codes are accepted for exactly the years `finsummaries` covers
and rejected afterwards, which is inverted from where the name path needs help:

```
2010-2018  District:  Senate, Plymouth & Norfolk (code 127)
2020       error: 127 is not a legislative (House/Senate) district code in 2020
```

2020 is the year where both paths are closed. The legislative feed for 2020
carries `districtCodeSought` 127 with `officeSought` `"Senate, Plymouth &
Norfolk"` — the tool already fetches it — and the same is true of code 140, which
`ocpf race` will *print* for 2020 and then refuse as input.

Tracked as issue #15, split out of #12. Five of the seven races
`bwbensonjr/election-modeling` still cannot resolve are this seat.

## What Changes

- **Consult the requested year's map before declaring a name ambiguous.** When
  the present map yields more than one match, resolution continues into the
  year-aware tiers instead of raising. A single match there wins. This is the
  whole of defect 1, and it is what makes the query expressible at all.
- **Prefer exact matches over substring matches within a tier.** `_match` already
  does this; the change is that it now gets the chance to run against the year's
  districts. `Plymouth and Norfolk` matches `Plymouth & Norfolk` exactly and the
  two current districts only as prefix extensions.
  **This must not collapse a genuine ambiguity**: `1st Suffolk` has *two* exact
  matches in every year's map (House 323 and Senate 130), so the rule is "exact
  matches beat substring matches", never "an exact match wins".
- **Report ambiguity in terms of the requested year.** Where the year's map
  cannot narrow the field either, the candidates listed are the year's, not the
  present map's, so the tool stops offering districts that did not exist in the
  year asked about.
- **Validate a numeric code against the requested year's map.** The code path
  gains the same tier-2 consult the name path has, so a code the feed reports for
  a year is accepted for that year. This closes the second half of #12: a code
  `ocpf race` prints is a code `ocpf race` accepts.

Out of scope, deliberately:

- **`--office house|senate`.** Idea 4 in the issue, and the issue rates it
  lowest: it does not help here, since both candidates are Senate. The genuine
  office collision (`1st Suffolk`) is already expressible by passing a code, and
  this change makes codes work in more years rather than fewer.
- **Fuzzy or subset name matching.** 2016 `Berkshire, Hampshire and Franklin`
  fails because OCPF calls that seat `Berkshire, Hampshire, Franklin & Hampden`
  in 2016 — the three-county name is the pre-2013 seat, code 141 in 2010. Both
  resolve correctly under their own era's name. Matching a stale label to a
  renamed seat is a different feature with a real false-positive cost.
- **Changing what counts as the present map.** No year threshold is introduced
  for "when the current map applies". The rule is uniform: a tier-1 ambiguity
  defers to the year's map, and in a current year that map is ambiguous too, so
  the ambiguity is still reported.
- **The `--special` gap noted in #12.** Filed there as not-a-bug and unchanged.

## Capabilities

### New Capabilities

None. This is behavior of district resolution, which the project specs under
`race-summary` alongside the command that uses it.

### Modified Capabilities

- `race-summary`: the "District resolution" requirement changes on two points —
  ambiguity is resolved against the requested year's map rather than the present
  one, and a numeric code is validated against the requested year's map. The
  guarantee that ambiguity is never guessed away is *kept*, and narrowed only by
  evidence tied to the year.

## Impact

- **Changed code**: `resolve_district` in `src/ocpf_cli/districts.py` — the
  tier-1 ambiguity branch and the numeric-code branch. No new endpoint and, for
  the name path, no new request in the common case: tier 2 is the feed `ocpf
  race` already fetches.
- **Cost**: a previously-ambiguous name now costs what a previously-unmatched
  name costs — tier 2, then possibly the tier-4 sweep for a pre-2020 year. That
  is a new cost on a path that currently fails fast. Names that resolve at tier 1
  today are untouched and make no additional request.
- **Behavior change, not breaking**: a query that errored as ambiguous may now
  succeed. A query that succeeds today cannot change answer, since tier 1 still
  short-circuits on a unique match. The ambiguity *error* changes which
  candidates it lists.
- **Docs**: `CLAUDE.md` gains the fact that the legislative feed is a usable
  source of era-correct district *codes* for 2020+, which is what makes the
  numeric path year-aware.

## Related

Closes bwbensonjr/ocpf-cli#15 and the remaining half of #12. Builds on the
year-aware tiers from `fix-district-resolution`,
`resolve-districts-from-report-log` and `name-districts-from-report-log`. The
comma-parsing fix in #16 is independent and already merged; it accounts for the
other #12 row that reported no match.
