## 1. Ordinal folding

- [ ] 1.1 Extend `districts._normalize` to fold ordinal words to digits
      (`first`->`1st` through at least `twentieth`), leaving `&`/`and` handling
      and word order untouched; verify unit tests cover `"First Plymouth &
      Norfolk"` resolving to the same district as `"1st Plymouth and Norfolk"`,
      and that `"Middlesex & Suffolk"` still does not match `"Suffolk and
      Middlesex"` (spec: "Ordinal words are folded to digits").
- [ ] 1.2 Confirm `uv run ocpf race "First Suffolk" --year 2026` resolves, and
      commit the fold on its own so a regression in it is bisectable separately
      from the year-aware index (design Decision 3).

## 2. Year-aware resolution signature

- [ ] 2.1 Change `resolve_district(query, districts=None)` to require a `year`
      argument and thread it from `commands/race.py`, with no default, so a
      caller cannot resolve against the wrong map by omission; verify existing
      `tests/test_districts.py` and `tests/test_race.py` pass with only the
      call-site change (design Decision 5).
- [ ] 2.2 Keep tier 1 first and short-circuiting: when the current `districts`
      reference answers, no other source is consulted; verify with a mocked API
      that resolving a current district issues exactly the `districts` request
      and no others (spec: "Current-map resolution is unchanged").

## 3. Era-correct names for 2020 and later

- [ ] 3.1 Add a parser turning a depository-feed `officeSought` string such as
      `"Senate, Worcester & Norfolk"` into an office and a normalized
      description; verify unit tests cover both the `&` and comma variants and a
      string with no comma.
- [ ] 3.2 Resolve a name against the feed's `officeSought` values for the
      requested year when tier 1 misses and `year >= 2020`, reusing the field
      `race` has already fetched rather than issuing a new request; verify with a
      2020 fixture that `"Worcester and Norfolk"` matches and that no extra HTTP
      call is made.
- [ ] 3.3 Record why the tier stops at 2020: verify against the live API that
      depository feed row counts are 428 (2020), 13 (2019), 2 (2018), 0 (2017),
      and note it in the module docstring.

## 4. Historical index for earlier years

- [ ] 4.1 Implement the `onballot/finsummaries/{year}/{code}` sweep over an
      office's code range, collecting populated codes with their `cpfId`s; verify
      against the live API that a 2010 Senate sweep returns 39 populated codes
      and that code 140 yields Moore (10315) and Roy (15242).
- [ ] 4.2 Label each populated code with its era-correct district via
      `filer/{cpfId}.officeSought`, preferring agreement across a code's filers
      when it has more than one; verify against the live API that filer 10315
      yields `districtCode` 140 and `districtDescription` `Worcester & Norfolk`
      (design Decision 1, tier 3).
- [ ] 4.3 Sweep Senate before House and short-circuit on a hit; verify with a
      mocked API that a Senate match issues no House probes (design Decision 2).
- [ ] 4.4 Emit progress to stderr during a sweep so a slow resolution is visibly
      working; verify stdout stays clean so `--json` output remains pipeable.
- [ ] 4.5 Verify end to end against the live API that
      `uv run ocpf race "Worcester and Norfolk" --year 2020` succeeds and reports
      that district's candidates, which is the invocation in issue #4.

## 5. Error messages

- [ ] 5.1 Distinguish "not a district name", "known but not in this year" (naming
      the years the name is known) and "ambiguous within the year"; verify each
      exits non-zero with its own message and that the second names at least one
      year (spec: "Retired district named for a year after its retirement",
      design Decision 4).
- [ ] 5.2 Verify `uv run ocpf race "Worcester and Norfolk" --year 2026` reports
      that the district did not exist in 2026 rather than that the name is not a
      legislative district.

## 6. Documentation

- [ ] 6.1 Record in `CLAUDE.md`: `districts` is the current map only and omits
      retired codes entirely (code 140 absent under any office), `districts/{year}`
      returns `[]`, `onballot/districts/{year}` is a 404, depository feed coverage
      starts at 2020, and `filer/{cpfId}.officeSought` carries an era-correct
      `districtCode` and `districtDescription`; verify by re-running each call
      cited.
- [ ] 6.2 Note the year-aware behavior in `README.md` under `ocpf race`,
      including that a pre-2020 retired-district lookup costs a code-range sweep;
      verify the documented invocation runs as written.
- [ ] 6.3 Add a CHANGELOG entry under an unreleased heading describing the fixed
      lookup and the ordinal folding.
- [ ] 6.4 Run `uv run pytest` and confirm the suite passes, with existing race
      and district tests changed only where the `year` argument is threaded.
