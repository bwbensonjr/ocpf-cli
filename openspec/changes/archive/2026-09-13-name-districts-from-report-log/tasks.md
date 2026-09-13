## 1. Generalize report-log access

- [x] 1.1 Change `_fetch_log_page` in `src/ocpf_cli/reports.py` to take a filter
  parameter dict instead of a bare `report_type_id`, keeping `StartIndex`
  1-based and `PageSize` at the module constant; verify the existing
  `tests/test_reports.py` log-paging tests still pass unchanged
- [x] 1.2 Reshape `fetch_report_log` into a filter-taking core with a
  `report_type_id` caller, so `fetch_special_reports` keeps its exact current
  behavior; verify by running `uv run python -m pytest tests/test_reports.py -q`
  and seeing no test change was needed
- [x] 1.3 Add `fetch_filer_log(cpf_id)` returning that filer's log rows via
  `CpfId`, reusing the paging core; verify with a respx-mocked two-page response
  that it pages from `StartIndex=1` and stops on the short page

## 2. Era-correct district naming

- [x] 2.1 Add a helper in `reports.py` that reduces a filer's log rows to the
  legislative `officeSought` strings whose parsed reporting period **ends** in a
  given year, dropping rows with an unparseable period or a non-legislative
  office; verify with a unit test covering a filer whose rows span two seats
  across different years (the cpfId 11448 shape) and one whose period straddles
  a year boundary
- [x] 2.2 Confirm the helper reads only `officeSought` and `reportingPeriod` —
  never a row's money or `amendmentDisplay`; verify by a test asserting that
  rows differing only in totals produce one office string, not several

## 3. Wire the fallback into tier 4

- [x] 3.1 In `_district_for_code` in `src/ocpf_cli/districts.py`, when the
  `filer/{cpfId}` tally is empty **and** the `finsummaries` roster was
  non-empty, tally the era-correct office strings from step 2.1 across the
  roster's filers and return the most-reported label paired with the code from
  the URL; verify with a monkeypatched test reproducing the 2014 Senate 104
  roster (Pacheco→170, Rosa→157) and asserting it resolves to
  `Senate, 1st Plymouth & Bristol` with code 104
- [x] 3.2 Leave the `districtCode != code` discard in the filer tally exactly as
  it is; verify the existing
  `test_district_for_code_prefers_the_label_most_filers_report` and the
  Brady/Diehl-style mislabeling guard still pass
- [x] 3.3 Gate the fallback so an empty `finsummaries` roster returns `None`
  before any log request; verify with a test that asserts zero log calls for an
  empty code, so the sweep's per-code cost is unchanged across the ~76 Senate
  and ~164 House probes
- [x] 3.4 Confirm a code whose tally succeeds makes no log request; verify with a
  test counting requests on the 2010 Senate 104 roster (Pottier and Saade still
  report 104)

## 4. End-to-end verification

- [x] 4.1 Verify `uv run ocpf race "1st Plymouth and Bristol" --year 2014`
  resolves to `Senate, 1st Plymouth & Bristol (code 104)` and renders Pacheco
  and Rosa, instead of erroring `was not a legislative district in 2014`
- [x] 4.2 Verify the same for `--year 2012`, `--year 2016` and `--year 2018`,
  each of which fails today
- [x] 4.3 Verify `--year 2010` and `--year 2011` still produce byte-identical
  output to the pre-change run (they resolve via the filer tally and must not
  change)
- [x] 4.4 Verify a spot-check of an unaffected retired district —
  `"Worcester and Norfolk" --year 2010`, which resolves to code 140 — is
  unchanged
- [x] 4.5 Run `uv run python -m pytest -q` and confirm the full suite passes

## 5. Documentation

- [x] 5.1 Record in `CLAUDE.md`, under the `reports/log` section, that
  `reports/log?CpfId=` carries an era-correct `officeSought` usable to name a
  district code for a year, that its `reportYear` is unreliable (`None` across
  all 331 rows for cpfId 11448) so the period is the year signal, and that this
  is the era-correct complement to the existing most-recent-office note on
  `filer/{cpfId}`; verify by re-reading the section for consistency with the
  surrounding facts
- [x] 5.2 Add a `CHANGELOG.md` entry for the fix; verify it names the observable
  behavior (retired districts resolve for years their candidates have all moved
  on from) rather than the internal tier mechanics
