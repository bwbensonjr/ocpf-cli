## ADDED Requirements

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

The system SHALL resolve the `<district>` argument to a single OCPF district code
using the API's `districts` reference. It SHALL accept either a raw numeric
district code or a name matched case-insensitively against district descriptions,
and it SHALL restrict matches to legislative offices (House and Senate).

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

#### Scenario: No match

- **WHEN** the district name matches no legislative district
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

### Requirement: YTD summary table

The system SHALL render the matched candidates as a table with, at minimum:
candidate name, party, an incumbent marker, year-to-date receipts, year-to-date
expenditures, and current cash on hand. Monetary values SHALL be shown as
formatted currency in the default (human) output.

#### Scenario: Table columns

- **WHEN** the summary renders in default output
- **THEN** each candidate row shows name, party, incumbent marker, receipts YTD,
  expenditures YTD, and cash on hand

#### Scenario: JSON output of the summary

- **WHEN** the user passes `--json`
- **THEN** the system emits the merged, filtered candidate records as JSON,
  including the underlying numeric monetary values

### Requirement: Election timeline context, not money segmentation

The system SHALL present primary and general elections as timeline context and
SHALL NOT split candidates' year-to-date money by election. It SHALL show the
primary and general election dates for the year (from the API filing schedule)
and the as-of reporting date of the underlying figures, and it SHALL present the
year-to-date money as the single cumulative figure the API provides.

#### Scenario: Election dates shown as context

- **WHEN** the summary renders in default output
- **THEN** the header shows the primary and general election dates for the year

#### Scenario: As-of date shown

- **WHEN** the summary renders in default output
- **THEN** the header indicates the as-of reporting date of the year-to-date
  figures (derived from the candidates' latest report end dates)

#### Scenario: Money is not segmented by election

- **WHEN** a district has both a primary and a general election in the year
- **THEN** each candidate's receipts, expenditures, and cash on hand are shown as
  a single cumulative year-to-date figure, not divided into primary and general
  amounts
