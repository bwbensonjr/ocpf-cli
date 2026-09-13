# race-summary Specification

## Purpose

Provide the `ocpf race` command, which produces a financial summary of the
legislative candidates in a given Massachusetts district: resolving the
district, fetching and merging the legislative report feeds, filtering to the
district's candidates, and rendering a summary table with election timeline
context.

By default the summary covers the regular election cycle with year-to-date
money. With `--special` it covers a special election held in the year instead,
drawn from the candidates' special-election filings, because the legislative
feeds carry no special elections at all.

## Requirements

### Requirement: `ocpf race` command

The system SHALL provide a command
`ocpf race <district> [--year <year>] [--special] [--stage primary|general]`
that produces a financial summary of the legislative (House or Senate)
candidates in a given district for a given election year.

Without `--special` the command summarizes the regular-cycle contest with
year-to-date money, exactly as before. With `--special` it summarizes a special
election held in that year instead, drawn from the candidates' special-election
filings.

#### Scenario: Summary for a district by name

- **WHEN** the user runs `ocpf race "Suffolk and Middlesex"` with the current
  year as the default
- **THEN** the system prints a summary table of the candidates in that district
  with their year-to-date receipts, expenditures, and cash on hand

#### Scenario: Explicit year

- **WHEN** the user passes `--year 2026`
- **THEN** the system produces the summary for the 2026 legislative filing year

#### Scenario: Default year

- **WHEN** the user omits `--year`
- **THEN** the system uses the current calendar year

#### Scenario: Special election requested

- **WHEN** the user runs `ocpf race "6th Bristol" --year 2013 --special`
- **THEN** the system prints the candidates who filed special-election reports
  for that district and year, with the money those filings report

#### Scenario: Regular-cycle behavior is unchanged

- **WHEN** the user omits `--special`
- **THEN** the system produces exactly the summary it produced before special
  elections were supported, from the same sources

#### Scenario: A year with no regular election points at the flag

- **WHEN** the user runs `ocpf race <district> --year <year>` without `--special`
  for a year in which the district had no regular election
- **THEN** the error names `--special` as the way to reach a special election
  held that year, rather than reporting only that no candidates were found

### Requirement: District resolution

The system SHALL resolve the `<district>` argument to the single OCPF district
the name identified **in the requested year**. It SHALL accept either a raw
numeric district code or a name matched case-insensitively against district
descriptions, and it SHALL restrict matches to legislative offices (House and
Senate).

A numeric district code SHALL be validated against the map for the **requested
year**, not only against the present map. A code that a year-scoped source
reports for that year SHALL be accepted for it. In particular, any district code
the system itself reports for a year SHALL be accepted as input for that year.

Name matching SHALL be tolerant of notation that varies between sources: `&` and
`and` are equivalent, and ordinal words (`First`, `Second`, `Third`) are
equivalent to their numeric forms (`1st`, `2nd`, `3rd`). Word order remains
significant.

A district that existed in the requested year SHALL be resolvable by name even
if it has since been retired at redistricting and no longer appears in the
current district reference. This SHALL hold for years in which no source of
district *codes* covers the requested year: where the districts that held a
special election that year are known by name from the candidates' filings, those
names SHALL be resolvable.

It SHALL also hold where the converse is true — the district *code* is
established for the requested year but no candidate who sought that seat still
reports it as the office they seek. Resolution SHALL NOT depend on whether a
seat's former candidates ran for it again. Where the candidates' current offices
cannot name such a code, the system SHALL establish the name from the office
recorded on the filings those candidates made in the requested year, which names
the seat as it stood when it was filed for.

A resolved district SHALL carry its district code whenever the code can be
established from a source that ties it to the requested year. Where a name is
known for the year but no such source reports a code, the district SHALL still
resolve, with its code absent. The system SHALL NOT substitute a code drawn from
a different year, and SHALL NOT report a district as non-existent on the grounds
that only its code is unknown.

Where a name matches more than one district in the present map, the system SHALL
NOT report that as ambiguous without first consulting the map for the requested
year. Where the year's map yields exactly one match, that district SHALL be
resolved. Ambiguity SHALL be reported only when the requested year's own map
cannot narrow the field, and the candidates offered SHALL be districts that
existed in that year.

Within any one map, an exact name match SHALL take precedence over a match that
is merely a prefix or substring. This precedence SHALL NOT collapse a genuine
ambiguity: where a name matches more than one district *exactly* — as a numbered
district name shared by a House and a Senate seat does — the result remains
ambiguous.

When a name cannot be placed in the requested year at all, the system SHALL say
so in terms of that year rather than asserting the name is not a legislative
district.

#### Scenario: Numeric code passed directly

- **WHEN** the user passes a value that is a valid legislative district code
- **THEN** the system uses that code without name matching

#### Scenario: A code the system prints is a code it accepts

- **WHEN** the system reports a district code for a year, such as code 140 for
  `"Worcester and Norfolk"` in 2020
- **THEN** passing that code for that same year resolves to the same district

#### Scenario: Retired code accepted for a year a year-scoped source reports it

- **WHEN** the user passes a district code that the present map omits but a
  year-scoped source reports for the requested year, such as code 127 for 2020
- **THEN** the system resolves it rather than reporting it is not a legislative
  district code in that year

#### Scenario: Unique name match

- **WHEN** the district name matches exactly one legislative district description
- **THEN** the system resolves to that district's code and proceeds

#### Scenario: Ambiguous name match

- **WHEN** the district name matches more than one legislative district in the
  requested year (e.g. `Middlesex` matches several)
- **THEN** the system prints the matching districts with their codes and offices
  and exits without guessing

#### Scenario: Retired name that prefixes two current district names

- **WHEN** the user requests a district whose name matches two districts in the
  present map only as a prefix, but exactly one district in the requested year's
  map — such as `"Plymouth and Norfolk"` for 2016 or 2020, which the present map
  splits into `1st Plymouth and Norfolk` and `2nd Plymouth and Norfolk`
- **THEN** the system resolves it to the single district of that name in the
  requested year rather than reporting it as ambiguous

#### Scenario: Ambiguity candidates are districts of the requested year

- **WHEN** a name is genuinely ambiguous for the requested year
- **THEN** the districts offered are ones that existed in that year, and the
  system does not suggest districts that did not

#### Scenario: An exact match does not collapse a genuine ambiguity

- **WHEN** a name matches more than one district exactly, such as `"1st Suffolk"`
  naming both a House and a Senate seat
- **THEN** the result remains ambiguous and the system exits without guessing

#### Scenario: Near-collision names are distinguished

- **WHEN** the user requests `"Suffolk and Middlesex"`
- **THEN** the system resolves to district 166 and does not confuse it with
  `"Middlesex & Suffolk"` (district 151)

#### Scenario: Retired district named for a year it existed

- **WHEN** the user requests a district that existed in the requested year but
  has since been retired at redistricting, such as `"Worcester and Norfolk"` for
  2020
- **THEN** the system resolves it to the code it held in that year and proceeds

#### Scenario: Retired district named for a year with no district-code source

- **WHEN** the user requests a district by the name it held in a year for which
  no district-code source has data, but in which it held a special election,
  such as `"2nd Hampden and Hampshire"` for 2013
- **THEN** the system resolves it rather than reporting that it was not a
  legislative district that year

#### Scenario: Code recovered from the candidates who sought the seat

- **WHEN** a district is resolved by name for such a year and at least one
  candidate who filed for that seat still reports it as the office they sought
- **THEN** the resolved district carries the code those candidates report

#### Scenario: Code unavailable for a district known by name

- **WHEN** a district is resolved by name for such a year but no candidate who
  filed for that seat still reports it as the office they sought
- **THEN** the district resolves with its code absent, and the system does not
  substitute a code the data does not tie to that year

#### Scenario: Seat named from the filings when every candidate has moved on

- **WHEN** the user requests a district by the name it held in a year for which a
  district-code source has data, but every candidate who sought that seat has
  since sought a different one — such as `"1st Plymouth and Bristol"` for 2014,
  whose candidates now report districts 170 and 157
- **THEN** the system resolves it to the code it held that year rather than
  reporting that it was not a legislative district that year

#### Scenario: Candidates who stayed put still name the seat

- **WHEN** at least one candidate who sought the seat still reports it as the
  office they seek
- **THEN** the system names the district from those candidates and makes no
  further request, resolving to the same district it resolved to before the
  filings were consulted

#### Scenario: A code that cannot be named is not reported as non-existent

- **WHEN** a district code carries candidates for the requested year but neither
  the candidates' current offices nor their filings for that year name it
- **THEN** the system does not assert that the district did not exist that year
  on the grounds that only its name is unknown

#### Scenario: Retired district named for a year after its retirement

- **WHEN** the user requests a retired district for a year in which it did not
  exist
- **THEN** the system reports that the district did not exist in that year,
  indicating the years in which the name is known, and exits non-zero

#### Scenario: Ordinal words are folded to digits

- **WHEN** the user requests `"First Plymouth & Norfolk"`
- **THEN** the system resolves it to the same district as `"1st Plymouth and
  Norfolk"`

#### Scenario: Current-map resolution is unchanged

- **WHEN** a district name resolves against the current district reference for a
  year in which the current map applies
- **THEN** the system resolves it to the same code it resolved to before
  year-awareness was introduced, without consulting any historical source

#### Scenario: No match

- **WHEN** the district name matches no legislative district in the requested
  year and is not known in any other year
- **THEN** the system prints an error indicating no match and exits non-zero

### Requirement: Legislative field fetch and merge

The system SHALL retrieve the legislative year-to-date field from both the
depository and non-depository legislative report feeds for the requested year and
merge them by `cpfId` so that a candidate appearing in either feed is included
exactly once.

#### Scenario: Candidate in depository feed

- **WHEN** a candidate files depository (bank) reports
- **THEN** their year-to-date figures from the depository feed are included

#### Scenario: Candidate only in non-depository feed

- **WHEN** a candidate appears only in the non-depository feed
- **THEN** they are still included in the merged field

#### Scenario: Candidate in both feeds is not duplicated

- **WHEN** a candidate appears in both feeds
- **THEN** the candidate appears exactly once in the results

### Requirement: District filtering

The system SHALL include a candidate in the output when the candidate's
`districtCodeSought` or `districtCodeHeld` equals the resolved district code.

Where the resolved district has no code, no candidate SHALL be matched by code.
A district known only by name carries no code to compare against, and treating
an absent code as matching a row whose own code is missing or zero would include
unrelated candidates.

#### Scenario: Candidate seeking the district

- **WHEN** a candidate's `districtCodeSought` equals the resolved code
- **THEN** the candidate is included

#### Scenario: Incumbent holding the district

- **WHEN** an incumbent's `districtCodeHeld` equals the resolved code
- **THEN** the candidate is included and marked as the incumbent

#### Scenario: Resolved district has no code

- **WHEN** the resolved district carries no code and candidate rows are filtered
  by code
- **THEN** no candidate is matched by code, rather than every candidate whose own
  code is absent or zero

#### Scenario: No candidates found

- **WHEN** no candidate matches the resolved district for the year
- **THEN** the system reports that no candidates were found and exits non-zero

### Requirement: Historical financial data fallback

When the current-cycle legislative feeds yield no candidate with money for the
resolved district and year, the system SHALL fall back to the district-scoped
`onballot/finsummaries/{year}/{districtCode}` endpoint and use its rows as the
candidate field. Selection SHALL be driven by data availability, not a hardcoded
year cutoff.

The system SHALL normalize each `finsummaries` row into the shared candidate-row
shape used by the current-cycle path: the currency strings `receipts`,
`expenditures`, and `endBalance` SHALL be parsed into the numeric fields
`receiptsYtdNumeric`, `expendituresYtdNumeric`, and `currentCashOnHandNumeric`
respectively, and the `isIncumbent` and `isWinner` flags SHALL be carried
through. Because `finsummaries` is district-scoped by URL and returns
`districtCode: 0` on every row, historical rows SHALL NOT be run through the
`districtCodeSought`/`districtCodeHeld` filter.

#### Scenario: Current feeds empty, historical data available

- **WHEN** the current-cycle feeds return no candidate with money for the
  resolved district (e.g. `ocpf race --year 2008 37th`)
- **THEN** the system fetches `onballot/finsummaries/{year}/{districtCode}` and
  renders the candidates from that feed

#### Scenario: Current feeds have data

- **WHEN** the current-cycle feeds return at least one candidate with money for
  the resolved district
- **THEN** the system uses the current-cycle field and does not call the
  `finsummaries` endpoint

#### Scenario: Currency strings normalized to numbers

- **WHEN** a `finsummaries` row reports `receipts` as `"$63,727.50"`
- **THEN** the normalized record carries `receiptsYtdNumeric` of `63727.50`, and
  likewise for expenditures and `endBalance` mapped to
  `currentCashOnHandNumeric`

#### Scenario: Incumbency from the flag

- **WHEN** a historical row has `isIncumbent` true
- **THEN** the candidate is marked as the incumbent, independent of
  `districtCode` (which is `0` in this feed)

#### Scenario: No candidates in either source

- **WHEN** neither the current-cycle feeds nor `finsummaries` return candidates
  for the resolved district and year
- **THEN** the system reports that no candidates were found and exits non-zero

### Requirement: YTD summary table

The system SHALL render the matched candidates as a table. For current-cycle
data the table SHALL include, at minimum: candidate name, party, an incumbent
marker, year-to-date receipts, year-to-date expenditures, and current cash on
hand. For historical (final-totals) data the table SHALL instead show
final-total column labels (`Raised` / `Spent` / `End Bal`) and add a winner
marker column driven by `isWinner`. Monetary values SHALL be shown as formatted
currency in the default (human) output.

#### Scenario: Table columns

- **WHEN** the summary renders current-cycle data in default output
- **THEN** each candidate row shows name, party, incumbent marker, receipts YTD,
  expenditures YTD, and cash on hand

#### Scenario: Historical table columns

- **WHEN** the summary renders historical (final-totals) data in default output
- **THEN** each candidate row shows name, party, incumbent marker, a winner
  marker, and final-total receipts, expenditures, and end balance, with the
  money columns labeled as final totals rather than YTD

#### Scenario: JSON output of the summary

- **WHEN** the user passes `--json`
- **THEN** the system emits the matched candidate records as JSON, including the
  underlying numeric monetary values; for historical data the records also
  include the `isWinner` flag

### Requirement: Election timeline context, not money segmentation

The system SHALL present primary and general elections as timeline context and
SHALL NOT split candidates' money by election. It SHALL show the primary and
general election dates for the year (from the API filing schedule) and, when the
underlying figures carry a reporting date, the as-of reporting date. It SHALL
present the money as the single cumulative figure the source provides.

This applies to the regular-cycle summary. A special-election summary is the
exception and is scoped to one election by construction: its figures come from
the filings covering that election's own reporting period, which is what makes
them meaningful. Such a summary SHALL name the period it covers and SHALL NOT
present an election date, which the API does not publish for special elections.

#### Scenario: Election dates shown as context

- **WHEN** the summary renders in default output
- **THEN** the header shows the primary and general election dates for the year

#### Scenario: As-of date shown for current-cycle data

- **WHEN** the summary renders current-cycle data in default output
- **THEN** the header indicates the as-of reporting date of the year-to-date
  figures (derived from the candidates' latest report end dates)

#### Scenario: No as-of date for historical data

- **WHEN** the summary renders historical (final-totals) data, which carries no
  report end date
- **THEN** the header omits the as-of line, and no lagging-filer note is shown

#### Scenario: Money is not segmented by election

- **WHEN** a district has both a primary and a general election in the year
- **THEN** each candidate's receipts, expenditures, and cash on hand (or end
  balance) are shown as a single cumulative figure, not divided into primary and
  general amounts

#### Scenario: Special-election money is scoped to that election

- **WHEN** the summary renders a special election in a year that also holds a
  regular election
- **THEN** the money shown covers the special election's own reporting period
  and excludes money reported for the regular contest later that year

#### Scenario: Special-election header names a period, not a date

- **WHEN** a special-election summary renders in default output
- **THEN** the header states the reporting period the figures cover and states
  no election date

#### Scenario: Candidates filed differing windows for one election

- **WHEN** the candidates in one special election filed reports covering
  different windows, as depository and non-depository filers routinely do
- **THEN** the header states the period spanning those windows and says the
  windows differ, rather than treating them as separate elections

### Requirement: Special election roster retrieval

The system SHALL determine which candidates contested a special election in a
district and year from the special-election reports those candidates filed,
rather than from the on-ballot or legislative-field feeds, which carry no
special elections. Retrieval SHALL cover both the non-depository and depository
forms of the special report types, and SHALL restrict results to legislative
offices.

#### Scenario: Roster for a year with no regular election

- **WHEN** the user requests a special election in a year whose regular-cycle
  feeds are empty
- **THEN** the system returns the candidates who filed special-election reports
  for that district, with their cpfIds

#### Scenario: Roster for a year that also held a regular election

- **WHEN** the user requests a special election in a year that also held a
  regular election in the same district
- **THEN** the system returns only the special election's candidates, not the
  regular contest's

#### Scenario: Both filing regimes are covered

- **WHEN** the candidates in a district filed under different filing regimes
- **THEN** the roster includes candidates from both, rather than only one

#### Scenario: District has no special election that year

- **WHEN** no candidate filed a special-election report for the district and year
- **THEN** the system reports that no special election was found for that
  district and year, and exits non-zero

#### Scenario: Non-legislative offices are excluded

- **WHEN** the underlying reports include special elections for offices that are
  not House or Senate
- **THEN** those candidates do not appear in a legislative district's roster

### Requirement: Special election money comes from the operative filing

The system SHALL take each candidate's special-election receipts and
expenditures from the operative version of that candidate's special-election
report — the version not superseded by a later amendment — and SHALL NOT report
figures from a superseded version.

#### Scenario: Amended filing reports the amended figures

- **WHEN** a candidate amended their special-election report one or more times
- **THEN** the figures shown are those of the latest operative version, not the
  version as originally filed

#### Scenario: Candidate filed no report for the requested stage

- **WHEN** a candidate appears in the roster but has no operative report for the
  requested stage
- **THEN** the system shows the candidate with their money marked as not
  reported, rather than omitting the candidate or showing zero

### Requirement: Special election stage selection

The system SHALL support a `--stage` option selecting between a special
election's primary and its general. When a district held both stages in the
requested year and no stage was given, the system SHALL summarize the general —
the election itself, of which the primary is a preliminary round — and SHALL
report that a primary was also held and how to reach it.

#### Scenario: Stage requested explicitly

- **WHEN** the user passes `--stage general`
- **THEN** the system summarizes the special general election, drawn from the
  pre-election special filings

#### Scenario: Only one stage exists

- **WHEN** the district held only one stage of a special election in the year and
  the user gives no `--stage`
- **THEN** the system summarizes that stage without requiring the option

#### Scenario: Both stages exist and no stage was given

- **WHEN** the district held both a special primary and a special general in the
  year and the user gives no `--stage`
- **THEN** the system summarizes the general, names the reporting period those
  figures cover, and reports that a special primary was also held and is
  reachable with `--stage primary`

#### Scenario: Requested stage was not held

- **WHEN** the user requests a stage the district did not hold that year
- **THEN** the system reports that the stage was not found and names the stage
  that was, and exits non-zero

### Requirement: Special election summary table

The system SHALL render a special election's candidates as a table showing, at
minimum, candidate name and the receipts and expenditures their operative filing
reports, with monetary values as formatted currency. The table SHALL be labeled
so that the figures are not mistaken for year-to-date amounts.

Where the district carries no code, the rendered header SHALL name the district
without asserting a code, and the JSON district code SHALL be null rather than a
placeholder value.

#### Scenario: Table columns

- **WHEN** a special-election summary renders in default output
- **THEN** each candidate row shows their name and the receipts and expenditures
  from their operative special-election filing, as formatted currency

#### Scenario: Money columns are labeled as period figures

- **WHEN** a special-election summary renders in default output
- **THEN** the money columns are labeled as the filing period's figures rather
  than as year-to-date figures

#### Scenario: JSON output of a special election summary

- **WHEN** the user passes `--json` with `--special`
- **THEN** the system emits the roster as JSON including each candidate's cpfId,
  the underlying numeric monetary values, the reporting period covered, and the
  identifier of the operative report each figure came from

#### Scenario: District without a code renders and serializes

- **WHEN** a special-election summary renders for a district resolved without a
  code
- **THEN** the header names the district and omits the code, and `--json` carries
  a null district code
