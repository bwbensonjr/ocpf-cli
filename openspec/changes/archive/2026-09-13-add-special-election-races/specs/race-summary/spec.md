## MODIFIED Requirements

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

## ADDED Requirements

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
