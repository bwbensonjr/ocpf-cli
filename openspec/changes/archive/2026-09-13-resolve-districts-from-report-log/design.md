## Context

See proposal.md — Why. The constraints that shape the approach, each measured
against the live API rather than assumed:

- **`onballot/finsummaries` has a two-part gap.** Zero rows for 2007, 2013, 2015,
  2017 and 2019, and zero from 2020 on; populated for 2004, 2006, 2008, 2010,
  2011, 2012, 2014, 2016 and 2018. Measured across Senate codes 105-145, not
  sampled. Tier 3 can only answer for a year in that populated set.
- **Tier 2 starts at 2020** (the legislative feed carries 428 rows in 2020, 13 in
  2019, 2 in 2018, 0 in 2017), so it cannot cover the gap below it.
- **The report-log sweep already holds the missing names.** `fetch_special_reports`
  returns rows pairing an era-correct `officeSought` with a parsed reporting
  period, so grouping by office and period year names every legislative seat that
  held a special in a year. It is memoized per process.
- **Sweep rows carry no district code.** This is the whole difficulty; everything
  below follows from it.
- **`filer/{cpfId}.officeSought` is MOST-RECENT office, not era-correct.** This
  is the fact that decides the design, and it contradicts the natural reading of
  the existing `CLAUDE.md` note, which says the endpoint "retains" a retired
  district. It retains it only for a filer who has not sought anything since.
  For the 2013 Senate 2nd Hampden & Hampshire roster:

  | cpfId | filer | `officeSought` today |
  |---|---|---|
  | 12646 | Bartley | House, 5th Hampden (246) |
  | 13888 | Humason | Mayoral, Westfield (4329) |
  | 14025 | Franco | Governor's Council, 8th District (1108) |
  | 15697 | Tautznik | **Senate, 2nd Hampden & Hampshire (114)** |

  One filer in four still names the seat. Humason went on to be mayor of
  Westfield; Bartley ran for a House seat.
- **A tally over a roster nonetheless recovers most codes.** Keeping only filers
  whose `districtDescription` still matches the seat recovers 3 of the 4 failing
  seat-years: 114 (Senate 2nd Hampden & Hampshire 2013), 128 (2nd Plymouth &
  Bristol 2015), 148 (1st Suffolk & Middlesex 2007). The fourth, Senate 1st
  Hampden & Hampshire 2013, has exactly one filer in the sweep and it is Franco.
- **Existing seam**: `districts._district_for_code` already tallies
  `filer/{cpfId}` this way and already discards filers reporting a different
  seat. The new tier needs the same technique seeded differently — by name and
  cpfId rather than by probing a code.

## Goals / Non-Goals

**Goals:**

- Make a district that held a special election resolvable for the year it held
  it, including the pre-2020 odd years no code source covers.
- Attach the real district code whenever the data ties one to that year.
- Never invent a code, and never report a district as non-existent merely
  because its code is unknown.
- Leave current-map resolution byte-identical, in behavior and request count.

**Non-Goals:**

- Resolving districts that held no special election in an uncovered year.
- Repairing `onballot/finsummaries`, or replacing tier 3 where it works.
- Building a general historical district map.

## Decisions

### 1. The new tier goes between tier 2 and tier 3

Order is cheapest-and-most-certain first: current map, then the year's feed, then
the log sweep, then the code-range sweep. Placing the log tier *above* tier 3
matters for more than correctness — tier 3 costs 76 Senate probes plus 164 House
probes and takes ~20-30 seconds, and today it runs to exhaustion before failing.
Answering from the memoized sweep first makes the affected lookups faster than
they are now, not slower.

Tier 3 is kept below rather than replaced: it answers for the even years the log
sweep does not cover, since a district that held no special has no sweep rows.

### 2. The code is recovered by tallying the seat's own filers

The sweep names a seat and lists the cpfIds that filed for it. Each
`filer/{cpfId}` is asked what office it sought; a filer whose
`districtDescription` no longer matches the seat is discarded, and the code the
survivors agree on wins.

Discarding is not a formality. Brady (14822) and Diehl (14907) both appear in the
Senate 2nd Plymouth & Bristol 2015 sweep rows and both now report *2nd Plymouth
and Norfolk* (code 169) — a different seat. Taking the modal code without the
description check would have returned 169 for a race in district 128.

*Alternative considered*: taking the code from the 2020 legislative feed when the
name matches there. It happens to agree where both work (114 and 148 both appear
in the 2020 feed under those names), which is exactly what makes it seductive.
Rejected because agreement is not derivation: it asserts that a same-named 2013
and 2020 seat are the same district across a redistricting, which is the claim
the year-aware resolution work exists to stop making. The tally, by contrast,
reads the code off filers who actually sought that seat.

### 3. `District.code` becomes optional

Three sources can name a district and only some can code it, so an `int` code is
no longer a property every resolved district has. Making it `int | None` states
that honestly.

The alternative — refusing to resolve a district whose code is unknown — keeps
the type simple at the cost of leaving a real race unreachable for a reason the
user cannot act on ("we know the district and the candidates, but not its
number"). The alternative of inventing a sentinel (`0`, `-1`) is worse: `0` is
already meaningful in this API, since `onballot/finsummaries` rows carry
`districtCode: 0`, and the historical-fallback requirement already exists to stop
that value being run through the code filter.

*Consequence, and the risk worth naming*: `code` is read in the race header, the
special-election header, `--json`, and `filter_by_district`. Each needs a None
path, and the filter is the dangerous one — see Risks.

### 4. The tier is seeded from the special-election sweep only

The sweep covers the special report types, so the tier names only seats that held
a special. That is a narrower fix than "resolve any historical district", and
deliberately so: it is exactly co-extensive with the years and seats that are
currently broken, because an odd year holds no regular contest, so a renamed
district with no special has nothing to report even if it resolved.

Widening this to every report type would multiply the sweep cost for seats that
would show an empty table. If a need for that appears, it is its own change.

### 5. The failure message keeps its year-relative shape

When the log does not know the name either, the existing error stands — it names
where the district *is* known rather than calling the name invalid. The only
change is that fewer names reach it.

## Risks / Trade-offs

- **An absent code silently matching everything** → `filter_by_district`
  compares `districtCodeSought`/`districtCodeHeld` against the resolved code. If
  that becomes `None` and a feed row's own code is missing, a naive `==` would
  match. The spec pins that no candidate is matched by code when the district has
  none, and this deserves a test rather than a careful read.
- **`--json` consumers** → `districtCode` becomes nullable. It is the documented
  break in the proposal; the field is present in the special-election records
  added in #8, which shipped one release ago, so exposure is small.
- **A recovered code is a claim about the past** → It comes from filers who
  sought that seat, which is the strongest available evidence, but a filer's
  record could itself be stale. Mitigated by the description check and by
  preferring agreement among filers; not eliminated.
- **One filer, no code** → Senate 1st Hampden & Hampshire 2013 resolves without a
  code today and would gain one the moment any of its filers' records named the
  seat. The behavior is therefore data-dependent and could change without a code
  change, which is worth stating in the docs so it does not read as a bug.
- **Sweep coverage bounds the fix** → The tier answers only for seats in the
  special-election sweep. A user asking for a renamed district in an odd year
  that held no special still gets the year-relative error. That is correct, but
  the error should not imply the district never existed.

## Open Questions

None. The one decision that shaped the specs — what to do when a district is
known by name but not by code — was settled before this was written: the district
resolves with its code absent.
