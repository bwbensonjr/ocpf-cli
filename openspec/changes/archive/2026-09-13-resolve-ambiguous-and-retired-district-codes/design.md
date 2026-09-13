## Context

See `proposal.md` — Why, for the defect and the measured evidence.

`resolve_district` runs four tiers, cheapest first, and both defects are in how
it *exits* those tiers rather than in the tiers themselves.

The name path:

```python
matches = _match(districts, target)        # tier 1: the present map
if len(matches) == 1: return matches[0]
if len(matches) > 1: raise _ambiguous(...) #  <-- never reaches tiers 2-4
year_districts = fetch_year_districts(year)  # tier 2 ...
```

An ambiguity found in the present map ends resolution, so a query that named a
year is answered entirely from a map that has no year. Everything needed is
already reachable — measured:

| source | matches for `plymouth and norfolk` |
|---|---|
| present map | 2 (both substring: `1st ...`, `2nd ...`) |
| 2020 feed (tier 2) | **1 exact** — code 127, `Plymouth & Norfolk` |
| 2016 sweep (tier 4) | **1** — code 127, `Plymouth & Norfolk` |
| 2024 feed | 2 substring, 0 exact — correctly ambiguous |

The numeric path has the mirror-image problem: it checks the present map, then
`_district_for_code`, which is backed by `finsummaries` and so returns nothing
from 2020 on. Tier 2 is never consulted for a code, though it carries
`districtCodeSought` for exactly those years.

## Goals / Non-Goals

**Goals:**

- Make the requested year decide, on both the name and the code path.
- Keep "ambiguity is never guessed away" exactly as strong as it is today —
  narrow the field only with evidence tied to the year, never by preference.
- Add no request to any lookup that already resolves.

**Non-Goals:**

- Fuzzy, subset or edit-distance name matching. Out of scope in the proposal and
  a different feature with a real false-positive cost.
- A year threshold for "when the present map applies". The tiers already encode
  era coverage; introducing a second notion of it invites the two to disagree.
- Reordering or merging the tiers. Only the exits change.

## Decisions

### Defer on ambiguity rather than special-casing the present map

**Decision:** on a tier-1 ambiguity, fall through to the year-aware tiers and
resolve there; report ambiguity only if the year's map is also ambiguous.

The alternative — "if the year is before the current map, skip tier 1" — needs a
cutoff year, and the redistricting boundary is not the same as `FIRST_FEED_YEAR`.
Two competing notions of "which era is this" would drift apart. Falling through
needs no cutoff: in a current year the year's map *is* the current field, so it
is ambiguous too and the error still fires. Verified on the 2024 feed, where
`Plymouth and Norfolk` has 0 exact and 2 substring matches.

This also makes the fix uniform with how a *missing* name is already handled. A
name absent from tier 1 falls through; a name over-present in tier 1 should too.
They are the same situation — tier 1 cannot answer for this year.

### Exact beats substring, but two exact matches stay ambiguous

**Decision:** keep `_match`'s existing precedence and let it run per tier.

The issue frames this as "let an exact match win", which read literally would
break `1st Suffolk` — it matches **two** districts exactly, House 323 and Senate
130, in every year's map including the present one. Verified. The correct rule is
the one `_match` already implements: exact matches as a set beat substring
matches as a set; a set of size > 1 is still ambiguous either way.

So no change to `_match` at all. The bug was never in the matcher — it was that
the matcher only ever saw the present map when the name was over-matched there.

### Report ambiguity from the year's candidates

**Decision:** when ambiguity survives, `_ambiguous` lists the year's districts.

Today the error for 2016 offers two districts that did not exist in 2016, and the
issue notes that following either suggestion produces "no candidates found". An
error whose every suggestion is a dead end is worse than no suggestions. Where
tier 2 or tier 4 produced a candidate set, that set is what the user can act on.

### Give the numeric path the tier-2 consult

**Decision:** between the present-map check and `_district_for_code`, consult
`fetch_year_districts(year)` for the code.

This is the minimal change that makes code acceptance uniform across eras.
`_district_for_code` stays as the pre-2020 source; the feed becomes the 2020+
source, exactly as on the name path. Order matters: the present map first (free),
then the feed (already fetched by `ocpf race`), then the sweep-backed lookup
(expensive).

The invariant worth stating in the spec is the user-visible one: **a code the
tool prints for a year is a code the tool accepts for that year.** Both sides now
read the same sources in the same order, so that holds by construction rather
than by coincidence.

## Risks / Trade-offs

- **A previously-ambiguous name now costs the tier-4 sweep before failing.** For
  a pre-2020 year with a genuinely ambiguous name, the error arrives ~20-30s
  later than today → Mitigation: it is the cost a *missing* name already pays,
  and the set of names that are ambiguous in the present map but absent from the
  year's map is small. Fast-failing with a wrong answer is not better.

- **A name could resolve differently than a user expects** if it is ambiguous
  today and unique in the year's map → Mitigation: that is the fix, and it cannot
  silently change a *working* lookup: tier 1 still short-circuits on a unique
  match, so anything that resolves today resolves to the same district.

- **Tier 2 returns districts keyed by code, first-wins per code.** A feed with
  two office strings for one code would keep the first → Mitigation: pre-existing
  behavior of `fetch_year_districts`, measured as no-conflict for 2020, and this
  change does not make it more load-bearing than the name path already does.

- **The numeric path may now accept a code for a year the user believes it did
  not exist.** → Mitigation: acceptance requires a year-scoped source to report
  it *for that year*, which is a stronger warrant than the present map offers.

## Migration Plan

None. No data migration, no config, no output-format change. A query that errors
today may succeed; none that succeed can change answer. Rollback is reverting the
commit.

## Open Questions

None.
