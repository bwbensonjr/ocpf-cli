# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Districts whose names contain commas are no longer dropped.** Every
  multi-county district — `Worcester, Hampden, Hampshire & Franklin`,
  `Middlesex, Suffolk & Essex`, `Berkshire, Hampshire & Franklin` — failed to
  resolve from the report log, reporting no match while the answer sat in the
  data. The office/district splitter assumed the first comma separated the two,
  which is the legislative feed's shape (`"Senate, Worcester & Norfolk"`) but not
  the log's (`"Senate Worcester, Hampden, Hampshire & Franklin"`), where the
  commas belong to the district name; those rows parsed as the office
  `"Senate Worcester"` and were discarded as non-legislative. The leading word
  now decides, falling back to the comma split only when it is not already an
  office. This restores 98 of 1,106 legislative special-election log rows and
  makes `ocpf race "Worcester, Hampden, Hampshire and Franklin" --year 2010`
  resolve to code 137. Single-county names, which have no comma, were never
  affected and are unchanged.

## [0.4.1] - 2026-09-13

A fix to historical district resolution. Districts retired at redistricting were
reachable only for the years one of their former candidates happened never to run
again — an accident of who stayed put, not a property of the data.

### Fixed

- **Retired districts now resolve for every year they were contested, not only
  the years a candidate stayed put.**
  `ocpf race "1st Plymouth and Bristol"` worked for 2010 and 2011 but failed for
  2012, 2014, 2016 and 2018 as though the seat had never existed, though OCPF
  returns its candidates for all six. Two independent causes, either one fatal:

  The historical code sweep ran the Senate from code 105, a range widened above
  the current map's ceiling but not below its floor, so retired code 104 was
  never probed. It now covers the retired codes below that floor.

  Where the sweep did reach a code, it could only name it by asking each
  candidate what office they seek *now* — which answers nothing once they have
  all moved on to other seats, as every candidate for this one had by 2012. The
  district code was never in doubt in those years; only its name was. Where a
  seat's former candidates can no longer name it, the name is now read from what
  their filings for that year called it, which is era-correct where their current
  office is not.

  Lookups that already resolved make no additional request, and return
  byte-identical output.

## [0.4.0] - 2026-09-13

Three new commands and a district resolver that understands history. The common
thread is reaching campaign-finance data the year-to-date feeds cannot express:
money bounded by an explicit window, the individual filings behind a cumulative
figure, and special elections — which those feeds carry none of at all.

### Added

- **`ocpf reports <filer>`** lists the reports a committee has filed —
  pre-election, pre-primary, post-election, special-election, mid-year,
  year-end, deposit and bank reports — with `--type`, `--year`,
  `--since`/`--until`, `--limit`, `--include-superseded` and `--json`. The
  listing covers the filer's whole filing history. `--type` matches the report
  type as a case-insensitive substring, so `--type "pre-election"` finds both the
  depository and non-depository spellings.
- **`ocpf report <report-id>`** shows one filing in full: header, schedule
  totals, amendment lineage and the canonical OCPF link, with `--schedule`
  (repeatable: `receipts`, `expenditures`, `out-of-pocket`, `in-kind`,
  `liabilities`, `subvendor`) to print line items, and `--json`.

  These two are the only view of an individual filing's reporting period. The
  year-to-date feeds behind `ocpf race` and `ocpf filer` carry one cumulative
  figure per filer per calendar year and are never segmented by election, so a
  single election's window does not exist in them.
- **`ocpf totals <filer> --start <date> --end <date>`** reports the record count
  and total a committee received or paid over an explicit closed window, with
  `--category receipts|expenditures` and `--json`. Both bounds are required and
  the window is reported alongside the figure, because a published year-to-date
  number covers a full calendar year and so includes money raised *after* the
  election — 28% of cpfId 14902's 2024 receipts and 70% of its 2020 receipts
  arrived after October 31.
- **`ocpf race <district> --year <year> --special`** summarizes a special
  election. The on-ballot and legislative feeds carry none, so a year with no
  regular contest previously looked empty: `ocpf race "6th Bristol" --year 2013`
  reported no candidates for a seat two people contested that September. The
  roster is built from the candidates' own special-election filings via a sweep
  of `reports/log`, the API's only cross-filer path, which reaches even years as
  well as odd — a district can hold a special in March and its regular contest
  the same November, with different rosters.

  `--stage primary|general` selects the stage, defaulting to the general and
  naming the primary when one was held. Money comes from each candidate's
  *operative* filing rather than the sweep rows, which return every amendment
  generation: reading those would have understated one 2013 candidate by 36%.
  The header names the reporting period the figures cover and asserts no election
  date, which OCPF does not publish for specials. `--json` carries each
  candidate's cpfId, numeric figures, filing window, and the id of the report
  each figure came from.
- Asking for a district in a year with no regular election now names `--special`
  in the error, rather than only reporting that no candidates were found.

### Changed

- **BREAKING (`--json` consumers): `districtCode` may now be `null`.** A district
  can be known by name and not by number. `filer/{cpfId}` reports a filer's most
  recent office sought, so a seat whose candidates have all since run for
  something else yields no code — Senate 1st Hampden & Hampshire 2013 is the live
  case. That district now resolves and reports with its code omitted from the
  header and `null` in JSON, rather than being reported as a district that never
  existed. Consumers reading `districtCode` from `ocpf race --json` should treat
  it as optional.

### Fixed

- **District names now resolve against the map for the requested year.** A
  district retired at redistricting could not be named even for a year in which
  it existed: `ocpf race "Worcester and Norfolk" --year 2020` failed as though
  the name were invalid, though it was a real Senate district through the 2011
  cycle. OCPF's `districts` reference is the present map only and omits retired
  codes entirely, so resolution now falls back to the legislative feed's
  era-correct `officeSought` (2020 onward) and, for earlier years, a sweep of the
  office's code range labelled from `filer/{cpfId}`. Failure is now reported in
  terms of the requested year, naming where the district did exist.
- **Districts renamed since a pre-2020 odd year now resolve for that year.**
  No source has district codes for 2007, 2013, 2015, 2017 or 2019 —
  `onballot/finsummaries` returns zero rows for those years and the legislative
  feed starts at 2020 — so a renamed district could not be named for the year it
  held a special, which is exactly what those years are for:
  `ocpf race "2nd Hampden and Hampshire" --year 2013 --special` failed as though
  the name were invalid, after paying a ~20-second code-range sweep to find out.
  Resolution now consults the special-election report log, which names the seats
  from the filings themselves, and recovers each seat's district code by tallying
  the filers who sought it. This reaches all four affected districts and skips
  the code-range sweep for them.
- Ordinal words are folded to the digit forms the API writes, so
  `"First Plymouth & Norfolk"` resolves like `"1st Plymouth and Norfolk"`.

## [0.3.0] - 2026-09-04

### Added

- `ocpf expenditures <filer>` lists and totals the payments a committee has
  made, with `--year`, `--since`/`--until`, `--vendor`, `--min-amount`/
  `--max-amount`, `--limit` and `--json`. `--by-vendor` totals by payee instead
  of listing records.

### Changed

- **A filter that matches nothing now exits zero** rather than non-zero. When a
  command retrieves a result set successfully and a user-supplied filter narrows
  it to nothing, that is reported on stdout as a finding and the command
  succeeds — so `ocpf expenditures <filer> --vendor "..."` distinguishes "this
  committee paid them nothing" from "the lookup failed". Input that resolves to
  nothing (an unknown district, a name matching no filer), bad input and API
  errors still exit non-zero. Scripts that treated any empty result as a failure
  need updating.

## [0.2.0] - 2026-07-23

### Added

- `ocpf --version` (and `-V`) prints the installed version and exits.

### Changed

- CI/release workflows: bumped GitHub Actions off Node 20 to current majors
  (`checkout` v7, `setup-uv` v9, `upload-artifact` v7, `download-artifact` v8).

## [0.1.0] - 2026-07-23

Initial release. Published to PyPI as [`ocpf`](https://pypi.org/project/ocpf/) —
installable and runnable with `uvx ocpf`, `pipx install ocpf`, or
`pip install ocpf`.

### Added

- `ocpf race <district> [--year] [--json]` — year-to-date financial summary of
  the legislative (House/Senate) candidates in a district: receipts,
  expenditures, and cash on hand, with primary/general election dates and the
  as-of reporting date as timeline context.
- `ocpf filer <filer> [--year] [--json]` — a single filer's committee profile,
  cumulative year-to-date finances, and most recent reports.
- District resolution by case-insensitive name (with `&`/`and` treated alike) or
  by raw numeric code; ambiguous names are listed rather than guessed.
- Historical race support: for pre-2020 cycles, where the current legislative
  feeds carry no money, `ocpf race` falls back to the district-scoped
  `onballot/finsummaries` endpoint, rendering final full-cycle totals
  (`Raised` / `Spent` / `End Bal`) with a winner (`W`) marker.
- `--json` output for both commands, emitting the underlying records (including
  numeric monetary values) to stdout while human status goes to stderr.

### Packaging

- MIT licensed; metadata, keywords, and classifiers for Python 3.11–3.13.
- Tag-driven versioning via `hatch-vcs`.
- Automated, test-gated release to PyPI via GitHub Actions using Trusted
  Publishing (OIDC), with CI running the test suite on Python 3.11–3.13.

[Unreleased]: https://github.com/bwbensonjr/ocpf-cli/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/bwbensonjr/ocpf-cli/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/bwbensonjr/ocpf-cli/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/bwbensonjr/ocpf-cli/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bwbensonjr/ocpf-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bwbensonjr/ocpf-cli/releases/tag/v0.1.0
