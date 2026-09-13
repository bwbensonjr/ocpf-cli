## 1. Year-aware numeric code validation

- [x] 1.1 In `resolve_district` in `src/ocpf_cli/districts.py`, insert a
  `fetch_year_districts(year)` lookup for a numeric code between the present-map
  check and `_district_for_code`; verify with a monkeypatched test that code 127
  resolves to `Senate, Plymouth & Norfolk` for 2020, where it errors today
- [x] 1.2 Verify the present-map check still short-circuits so a current code
  makes no feed request; assert zero `fetch_year_districts` calls for a code in
  the present map
- [x] 1.3 Verify the pre-2020 path is unchanged — `_district_for_code` still
  answers for a year `finsummaries` covers, and code 140 still resolves for 2010

## 2. Defer ambiguity to the requested year

- [x] 2.1 Change the tier-1 ambiguity branch so it records the present-map
  candidates and falls through to the year-aware tiers instead of raising;
  verify with a test that a name matching two present-map districts and one
  year-map district resolves to the year's district
- [x] 2.2 Confirm `_match`'s exact-beats-substring precedence is used unchanged
  per tier — no edit to `_match`; verify `1st Suffolk`, which has two *exact*
  matches (House 323, Senate 130), is still reported ambiguous
- [x] 2.3 Verify a unique tier-1 match still short-circuits with no extra
  request, so no currently-resolving lookup changes answer or cost
- [x] 2.4 Verify a name ambiguous in a current year still errors — the 2024 feed
  has 0 exact and 2 substring matches for `Plymouth and Norfolk`, so the
  fall-through must reach the ambiguity error, not resolve

## 3. Report ambiguity in terms of the requested year

- [x] 3.1 Make the surviving ambiguity error list the requested year's
  candidates rather than the present map's; verify with a test asserting the
  2016 error does not offer districts 167 and 169
- [x] 3.2 Verify the error still exits non-zero and still names every candidate
  with code and office, per the existing `race-summary` scenarios

## 4. End-to-end verification

- [x] 4.1 Verify `ocpf race "Plymouth and Norfolk"` resolves to code 127 for
  2010, 2012, 2016 and 2018 — the four rows of #12 that this change targets
- [x] 4.2 Verify it resolves for 2020, the year the issue identifies as having
  no path by either name or code
- [x] 4.3 Verify `ocpf race 127 --year 2020` and `ocpf race 140 --year 2020` both
  resolve, closing part 2 of #12
- [x] 4.4 Verify `ocpf race "1st Suffolk" --year 2024` still reports ambiguity
  and exits non-zero
- [x] 4.5 Re-run the lookups fixed in 0.4.1 and #16 — `1st Plymouth and Bristol`
  for 2010/2012/2014/2016/2018, `Worcester, Hampden, Hampshire and Franklin` for
  2010, `Worcester and Norfolk` for 2010 and 2020 — and confirm output is
  byte-identical
- [x] 4.6 Run `uv run python -m pytest -q` and confirm the full suite passes

## 5. Documentation

- [x] 5.1 Record in `CLAUDE.md` that the legislative YTD feed is a usable source
  of era-correct district *codes* for 2020+, alongside the existing note that it
  carries era-correct names — this is what makes the numeric path year-aware;
  verify the section reads consistently with the surrounding facts
- [x] 5.2 Add a `CHANGELOG.md` entry naming the observable behavior: a retired
  district whose name prefixes current ones is reachable, and a code the tool
  prints is a code it accepts
