## 1. Optional district code

- [x] 1.1 Change `District.code` to `int | None` in `src/ocpf_cli/districts.py`
      and make `District.label` render without a code when it is absent; verify
      unit tests cover both the coded and uncoded label forms.
- [x] 1.2 Make `filter_by_district` match nothing when the resolved code is None,
      rather than matching rows whose own `districtCodeSought`/`districtCodeHeld`
      is absent or zero; verify with a fixture holding rows with a missing code
      and a `districtCode: 0` row that neither is returned (spec: "Resolved
      district has no code").
- [x] 1.3 Give every other reader of `District.code` a None path — the race
      header, the special-election header, and both `--json` shapes — emitting a
      null district code rather than a placeholder; verify `--json` parses and
      carries `null` (spec: "District without a code renders and serializes").
- [x] 1.4 Run `uv run pytest` and confirm the existing suite still passes with
      the type widened, fixing any call site the type change surfaces.

## 2. Report-log resolution tier

- [x] 2.1 Add a function to `districts.py` that groups
      `reports.fetch_special_reports` rows into `(office, description, year)`
      seats with their cpfIds, parsing `officeSought` with the existing
      `_parse_office_sought` and discarding non-legislative offices; verify a
      fixture containing a `Municipal, Worcester` row produces no seat.
- [x] 2.2 Match a normalized query against those seats for the requested year,
      reusing `_normalize` so `"2nd Hampden and Hampshire"` matches the sweep's
      `Senate 2nd Hampden & Hampshire`; verify the ampersand and ordinal-word
      forms both match, and that matching is exact rather than substring (a
      substring match would let `"1st Suffolk"` hit `"21st Suffolk"`).
- [x] 2.3 Report a query matching more than one seat in the year as the existing
      ambiguity error rather than picking one; verify with a fixture holding two
      matching seats that the command exits non-zero and lists both.

## 3. Code recovery from the seat's filers

- [x] 3.1 Recover a seat's district code by tallying `filer/{cpfId}` over the
      seat's cpfIds, keeping only filers whose `districtDescription` still
      matches the seat and whose office matches; verify against the live API that
      Senate 2nd Hampden & Hampshire 2013 yields 114, 2nd Plymouth & Bristol 2015
      yields 128, and 1st Suffolk & Middlesex 2007 yields 148.
- [x] 3.2 Add a regression test pinning that a filer who has since sought a
      different seat cannot supply the code: with a fixture holding Brady (14822)
      and Diehl (14907) reporting `2nd Plymouth and Norfolk` (169) alongside two
      filers reporting `2nd Plymouth & Bristol` (128), the recovered code is 128;
      verify it fails if the description check is removed (design Decision 2).
- [x] 3.3 Resolve a seat whose filers all report a different office with its code
      absent rather than failing; verify against the live API that Senate 1st
      Hampden & Hampshire 2013 — whose only sweep filer, Franco (14025), now
      reports Governor's Council — resolves and renders (spec: "Code unavailable
      for a district known by name").

## 4. Tier ordering

- [x] 4.1 Insert the log tier between the year-feed tier and the code-range
      sweep in `resolve_district`; verify with a mocked API that a name answered
      by the current map still issues no extra request, and that a name answered
      by the log tier never reaches `onballot/finsummaries` (spec: "Current-map
      resolution is unchanged", design Decision 1).
- [x] 4.2 Confirm the affected lookups got faster rather than slower: time
      `uv run ocpf race "2nd Hampden and Hampshire" --year 2013 --special`,
      verify it prints no `Searching Senate districts...` lines, and record the
      measured split -- the sweep is the bulk of it and is memoized, so recover
      codes only for the seats that matched rather than every seat in the year.
- [x] 4.3 Verify tier 3 still answers for a year the log tier does not cover:
      `uv run ocpf race "Worcester and Norfolk" --year 2020` still resolves to
      Senate code 140 (spec: "Retired district named for a year it existed").

## 5. End-to-end and regression

- [x] 5.1 Verify all four previously failing invocations now succeed:
      `2nd Hampden and Hampshire`/2013, `1st Hampden and Hampshire`/2013,
      `2nd Plymouth and Bristol`/2015 and `1st Suffolk and Middlesex`/2007, each
      with `--special`, rendering a roster.
- [x] 5.2 Verify a name the log does not know still fails with the year-relative
      error rather than a claim that the name is not a legislative district
      (spec: "No match", design Decision 5).
- [x] 5.3 Pin that the regular-cycle path is untouched: verify `ocpf race`
      without `--special` for a current-map district issues exactly the requests
      it issued before this change, and that no existing race or district test
      required modification.
- [x] 5.4 Run `uv run pytest`, and run it again under `CI=true
      GITHUB_ACTIONS=true`, confirming both pass — rich styles CLI error text
      differently under that environment, which has broken a pull request in this
      repo before.

## 6. Documentation

- [x] 6.1 Correct the `CLAUDE.md` claim that `filer/{cpfId}.officeSought`
      "retains" a retired district: it reports the filer's **most recent** office,
      so it retains the old seat only for a filer who has sought nothing since.
      Record the 2013 Senate 2nd Hampden & Hampshire roster as the evidence (one
      filer in four still names the seat) and that this is why a tally is needed;
      verify by re-running the four `filer/{cpfId}` lookups cited.
- [x] 6.2 Record the new tier in `CLAUDE.md`'s resolution-tier list, including
      that it is seeded from the special-election sweep and so answers only for
      seats that held a special, and that a district may resolve without a code.
- [x] 6.3 Document in `README.md` that a district may render without a code, what
      that means, and that the pre-2020 odd-year lookups no longer pay the
      code-range sweep; verify the documented commands run as written.
- [x] 6.4 Add a CHANGELOG entry under an unreleased heading, marking the nullable
      `districtCode` in `--json` as a breaking change for consumers.
