## Why

A year with no regular legislative election returns no candidates, so the
special elections held in it are invisible:

```
$ ocpf race "6th Bristol" --year 2013
error: No candidates found for House, 6th Bristol (code 214) in 2013
```

Carole Fiola and David Steinhof contested the 2013-09-10 special for that seat.
The regular-cycle year *after* it shows them; the year they actually ran in shows
nothing. Fifteen races in `bwbensonjr/election-modeling`'s table fall in these
years, all specials.

The on-ballot and legislative feeds are keyed to the regular election cycle, and
nothing in them carries a special. But the filings do, and two earlier changes
now make them reachable: `ocpf reports` (PR #5) put the per-filer report path in
place, and year-aware district resolution (PR #7) made a district name resolve
for the year it was asked about.

**A fallback is not enough.** The obvious design — when the regular feeds come
back empty, look for a special — only covers odd years. Of the 1,119 special
pre-primary and pre-election report rows OCPF holds, **406 fall in even years**,
where the regular feed is populated and a fallback would never fire. In 2014 six
districts had both: House 5th Suffolk ran a special in March (Carvalho,
Charles-Peterson, Johnson, Lawton) and the regular contest in September and
November. Same district, same year, two different rosters. Only an explicit
selector can tell them apart.

## What Changes

- Add `--special` and `--stage primary|general` to `ocpf race`:

  ```bash
  ocpf race "6th Bristol" --year 2013 --special
  ocpf race "5th Suffolk" --year 2014 --special --stage general
  ```

  Without `--special`, behavior is unchanged in every respect.
- **Build the roster from a cross-filer report sweep.** `reports/log` is the only
  cross-filer path in the API, its filters fail *closed* (an unknown
  `ReportTypeId` returns `[]`, unlike `search/items`), and a full sweep of the
  special report types is two requests each: `ReportTypeId=22` (pre-primary
  special, 563 rows) and `23` (pre-election special, 556 rows), plus their
  depository equivalents. Grouping those rows by `officeSought` reconstructs the
  district rosters for exactly the years the feeds return nothing. Verified
  against the cpfIds issue #3 names: House 6th Bristol 2013 yields Fiola (13597)
  and Steinhof (15658); Senate 1st Suffolk yields Forry (14359) and Ureneck
  (14412); Senate 2nd Hampden & Hampshire yields Bartley (12646) and Humason
  (13888). It also recovers Leah Cole (15567) and Daniel M. Donahue (15637), the
  two candidates a cross-year name index matched to the wrong people.
- **Take the money from each candidate's operative filing, never from the sweep
  rows.** This is not a refinement; reading totals off the sweep produces wrong
  numbers. Steinhof filed four pre-election special reports for the same period —
  $9,940.00 as filed, then amendments to $13,030.00 and $13,530.00 — and the
  sweep returns all four. Picking the original understates him by 36%.
  `reports.fetch_reports()` already defaults to `OnlyCurrent=true` and returns
  exactly one operative report per candidate with the amended totals, so the
  money comes from there.
- **Show the reporting window, not an election date.** OCPF does not publish
  special election dates: `filingSchedules/2013` returns empty strings for both
  `primaryElectionDate` and `generalElectionDate`. The header therefore names the
  period the filings cover, which is sourced, and asserts no election date, which
  is not.
- **Report the money as the filing's own period total**, replacing the
  year-to-date columns for this view. A special held in March 2014 sits inside a
  calendar year that also contains a September primary and a November general;
  a year-to-date figure under a special-election heading would assert that money
  belongs to the special when most of it does not. This is the same error
  `ocpf totals` was built to avoid.
- **Default to the general, refuse to guess between two specials.** Holding both
  stages is the ordinary case — 64 of the 80 legislative district-years in the
  sweep, House 6th Bristol 2013 among them — so `--stage` is not required to
  reach one. Without it the command summarizes the general, the election itself,
  and reports that a primary was also held. What it will not guess at is two
  distinct reporting periods *within* one stage, meaning two separate specials in
  one district and year: those are reported as an ambiguity naming the windows
  found, the same contract district and filer resolution already follow.
- Make `ocpf race <district> --year <odd year>` name `--special` in its error
  rather than reporting that no candidates were found, so the failing invocation
  from issue #3 points at its own fix.

Out of scope, deliberately:

- **A general-purpose cross-filer report search.** The sweep is wired for the
  special report types this command needs. `reports/log` supports `Name` and an
  unfiltered `ReportTypeId` for other questions, and those deserve their own
  surface.
- **Regular primaries.** `--stage` selects between a special's primary and
  general. Splitting a *regular* cycle's money at the September primary is a
  different question, answerable today with `ocpf totals --start/--end`, and it
  would change the meaning of the default `ocpf race` view rather than adding to
  it.
- **Special elections for non-legislative offices.** The sweep returns municipal
  and Governor's Council rows; this command stays legislative, as `ocpf race`
  already is.
- **Inferring the election date** from the reporting window. The filing period
  ends days before the election, so any date derived from it would be a guess
  presented as a fact.

## Capabilities

### Modified Capabilities
- `race-summary`: the `ocpf race` command requirement gains the `--special` and
  `--stage` options; the "Election timeline context, not money segmentation"
  requirement gains a carve-out, because for a special the money **is** scoped to
  one election's reporting period, which is what makes the figure meaningful.
  The change also adds requirements for roster retrieval, operative-filing money,
  stage selection and ambiguity, and the special-election table.

### New Capabilities

None. Everything here is behavior of the existing `ocpf race` command, and the
project's specs are organized per command surface.

## Impact

- **New code**: a cross-filer sweep in `src/ocpf_cli/reports.py` (the report-log
  client, alongside the per-filer path already there) and a special-election
  roster path in `src/ocpf_cli/commands/race.py`.
- **Reused foundation**: `reports.fetch_reports` for operative filings,
  `districts.resolve_district` (now year-aware), `render`, and `api.get_json`.
- **External API**: four sweep requests for the roster, cached for the
  invocation, plus one `reports/reportList` call per candidate — rosters run two
  to eight people. A sweep is ~1,100 rows and is not filterable by year or
  district server-side, so the year and district narrowing happens locally.
- **Display-string parsing, confined here**: the log's `reportingPeriod` arrives
  in several shapes and `amendmentDisplay` contains literal HTML (`<br>Amendment`).
  `reports.py` documents this and the per-filer path deliberately avoids it; the
  sweep cannot, so the parsing belongs in the sweep and must not leak back.
- **Docs**: `CLAUDE.md` gains the sweep contract and the amendment hazard;
  `README.md` documents the flags with the 2013 example.
- **No breaking changes**: `ocpf race` without `--special` is untouched.

## Related

Closes bwbensonjr/ocpf-cli#3, the last of the three open issues. Depends on
already-merged work: `ocpf reports` (#5) for operative filings and year-aware
district resolution (#7) for matching a typed `"Worcester and Norfolk"` against
the sweep's `Senate Worcester & Norfolk`.
