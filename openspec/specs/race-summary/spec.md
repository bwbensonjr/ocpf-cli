# race-summary Specification

## Purpose

Provide the `ocpf race` command, which produces a year-to-date financial summary
of the legislative candidates in a given Massachusetts district: resolving the
district, fetching and merging the legislative report feeds, filtering to the
district's candidates, and rendering a summary table with election timeline
context.

## Requirements

### Requirement: `ocpf race` command

The system SHALL provide a command `ocpf race <district> [--year <year>]` that
produces a year-to-date financial summary of the legislative (House or Senate)
candidates in a given district for a given election year.

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

### Requirement: District resolution

The system SHALL resolve the `<district>` argument to the single OCPF district
code that district had **in the requested year**. It SHALL accept either a raw
numeric district code or a name matched case-insensitively against district
descriptions, and it SHALL restrict matches to legislative offices (House and
Senate).

Name matching SHALL be tolerant of notation that varies between sources: `&` and
`and` are equivalent, and ordinal words (`First`, `Second`, `Third`) are
equivalent to their numeric forms (`1st`, `2nd`, `3rd`). Word order remains
significant.

A district that existed in the requested year SHALL be resolvable by name even
if it has since been retired at redistricting and no longer appears in the
current district reference. When a name cannot be placed in the requested year,
the system SHALL say so in terms of that year rather than asserting the name is
not a legislative district.

#### Scenario: Numeric code passed directly

- **WHEN** the user passes a value that is a valid legislative district code
- **THEN** the system uses that code without name matching

#### Scenario: Unique name match

- **WHEN** the district name matches exactly one legislative district description
- **THEN** the system resolves to that district's code and proceeds

#### Scenario: Ambiguous name match

- **WHEN** the district name matches more than one legislative district (e.g.
  `Middlesex` matches several)
- **THEN** the system prints the matching districts with their codes and offices
  and exits without guessing

#### Scenario: Near-collision names are distinguished

- **WHEN** the user requests `"Suffolk and Middlesex"`
- **THEN** the system resolves to district 166 and does not confuse it with
  `"Middlesex & Suffolk"` (district 151)

#### Scenario: Retired district named for a year it existed

- **WHEN** the user requests a district that existed in the requested year but
  has since been retired at redistricting, such as `"Worcester and Norfolk"` for
  2020
- **THEN** the system resolves it to the code it held in that year and proceeds

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

#### Scenario: Candidate seeking the district

- **WHEN** a candidate's `districtCodeSought` equals the resolved code
- **THEN** the candidate is included

#### Scenario: Incumbent holding the district

- **WHEN** an incumbent's `districtCodeHeld` equals the resolved code
- **THEN** the candidate is included and marked as the incumbent

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
