## Context

See proposal.md — Why. Constraints, all verified against the live API:

- **`districts` is the present map and nothing else.** 365 rows; 200 legislative
  (160 House codes 201-364, 40 Senate codes 105-170). Code 140 appears under *no*
  office. The only row matching both "Worcester" and "Norfolk" is code 163,
  `Norfolk, Worcester and Middlesex` — a different seat.
- **No year-scoped district list exists.** `districts/{year}` returns `[]`;
  `onballot/districts/{year}` is a 404.
- **`filer/{cpfId}` retains an era-correct district with its code.** For cpfId
  10315 (Richard T. Moore, left the Senate 2014): `officeSought.districtCode` is
  140 and `officeSought.districtDescription` is `Worcester & Norfolk`. This is
  the cheapest handle on a retired district and the issue did not know it
  existed.
- **The depository YTD feed carries an era-correct `officeSought` string**, but
  its coverage starts abruptly at 2020: 428 rows in 2020, 431 in 2021, and
  13 in 2019, 2 in 2018, 0 in 2017 and 2013. So it answers for 2020+ and nothing
  earlier.
- **`onballot/finsummaries/{year}/{code}` answers per code**, which `race`
  already uses as its pre-2020 fallback. A 2010 Senate sweep of codes 105-180
  returns rows for 39 codes. Rows carry `cpfId` and `filerName` but
  `districtCode: 0` and no district name, so the code is known only from the URL
  that produced it and the name only from the filers it names.
- **Existing seam**: `districts.resolve_district(query, districts=None)` takes no
  year, and `_normalize` already folds `&`/`and`.

## Goals / Non-Goals

**Goals:**

- Resolve a district name to the code it held in the requested year.
- Never assert that a name is not a district when it was one.
- Leave current-map resolution byte-identical and request-identical.

**Non-Goals:**

- Tracking a seat's geographic continuity across redistricting. Names resolve
  within a year; whether the 2020 and 2024 6th Bristol are "the same seat" is
  outside what the API can support.
- A complete historical district gazetteer. The index answers the query asked,
  for the year asked, and is built no further.
- Non-legislative offices.

## Decisions

### 1. Tiered resolution, cheapest first, current map unchanged

`resolve_district(query, year)` tries in order:

1. **Current `districts` reference.** Exactly today's behavior. If it answers,
   nothing else is consulted and no extra request is made. This keeps the common
   case — a current district in a current year — free, and it is what the
   "Current-map resolution is unchanged" scenario pins.
2. **Depository feed `officeSought`**, for `year >= 2020`. `race` has already
   fetched this field for the same year, so the strings are in hand; parsing
   `"Senate, Worcester & Norfolk"` into office and description costs nothing.
   This tier has no codes, so a match here yields a *name*, and the code comes
   from tier 3 for one of its filers.
3. **`onballot/finsummaries/{year}/{code}` sweep plus `filer/{cpfId}`.** For each
   code in the office's range, one probe; for each populated code, one filer
   lookup to learn the era-correct name. Expensive and therefore last and lazy.

*Alternative considered*: building a full historical index once and caching it to
disk. Rejected for this change — a cache is state, invalidation policy and a new
failure mode, and the CLI has none of that today. If tier 3 proves too slow in
practice that is a follow-up with its own design, not something to bolt on here.

### 2. The office is inferred, not asked for

Tier 3's cost depends on which code range is swept: 76 probes for Senate,
164 for House. The user has not said which office they mean. Rather than adding
an `--office` flag, the resolver sweeps **Senate first, then House**: the Senate
range is less than half the size, and retired-district queries skew Senate
(all five 2011-cycle districts that fail name lookup today are Senate seats).
A hit in the first range short-circuits the second.

*Alternative considered*: requiring `--office` for historical years. Rejected as
pushing an implementation cost onto the user for a question they did not ask;
the flag would exist only to make our sweep cheaper.

### 3. Ordinal folding lands in `_normalize`, ahead of everything else

`_normalize` gains a word-to-digit fold (`first`→`1st` … at least through
`twentieth`, covering the numbered House and Senate districts). It is a pure
function with no network cost, it fixes real lookups on its own, and it is
independent of the year-awareness work — so it ships as its own commit and its
own tests, and a regression in it is bisectable separately from the index.

Folding is one-directional (words to digits) because the API always writes
digits, so digits are the canonical form.

### 4. The error distinguishes three cases

Today there is one failure message. There will be three:

- **Not a district name at all** — unchanged wording.
- **Known, but not in this year** — names the years the district is known in, so
  the user can retry. This is the case the issue is actually about.
- **Ambiguous within the year** — the existing candidate-list behavior, extended
  to historical candidates.

The middle case is the point of the change: a resolver that knows a name existed
and still says "matches no legislative district" is the bug being fixed.

### 5. Year flows from the command, with no new default

`commands/race.py` already computes the year it reports on and passes it down.
`resolve_district` takes it as a required argument rather than defaulting to the
current year, so a caller cannot accidentally resolve a 2013 query against the
2026 map — which is the class of error this change exists to remove.

## Risks / Trade-offs

- **Tier 3 is slow** — up to 240 requests for a House query in a pre-2020 year →
  Mitigated by ordering (most queries never reach it), by the Senate-first sweep,
  and by progress output to stderr so a slow resolution is visibly working rather
  than hung. Accepted rather than cached; see Decision 1.
- **Tier 3 identifies a district by its filers** — a year in which a district had
  no filers is invisible to it → Such a district also has no race to report, so
  `race` would have nothing to show even with the code. The error message says
  no candidates were found for that year, which is already the behavior.
- **Two districts sharing a surname in one year** → The index holds one to eight
  filers per district-year, so descriptions are distinct within a year; the
  ambiguity that defeats a *statewide cross-year* name index does not arise
  within a single year. Where two do match, the existing ambiguous-match path
  prints both.
- **`filer/{cpfId}` reports the district a filer last sought**, not necessarily
  the one they sought in the queried year → A filer who moved districts could
  mislabel a code. Mitigated by taking the label from a filer the sweep found *at
  that code in that year*, and by preferring agreement across that code's filers
  when it has more than one.

## Open Questions

None.
