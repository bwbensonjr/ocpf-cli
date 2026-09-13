# report-list Specification

## Purpose

Provide the `ocpf reports` command, which lists the reports a single OCPF filer
has filed — pre-election, pre-primary, post-election, special-election, mid-year,
year-end, deposit, and bank reports alike — so that a user can find a particular
filing, see its reporting period and totals, and learn the report id needed to
read it in full.

## Requirements

### Requirement: `ocpf reports` command

The system SHALL provide a command `ocpf reports <filer>` that lists the reports
a single OCPF filer has filed, most recent first, together with the number of
reports shown.

#### Scenario: Reports listed for a filer

- **WHEN** the user runs `ocpf reports 14819`
- **THEN** the system prints that filer's reports, each showing at minimum the
  report id, the report type, the reporting period, and the date filed, followed
  by the count of reports shown

#### Scenario: Report identifier is shown for every report

- **WHEN** the listing renders in default output
- **THEN** every row includes the report's numeric identifier, so that the user
  can pass it to `ocpf report <report-id>`

#### Scenario: Most recent first

- **WHEN** the listing renders without an explicit ordering request
- **THEN** the reports appear in descending order of filing recency

#### Scenario: Filer has filed no reports

- **WHEN** the resolved filer has filed no reports at all
- **THEN** the system reports that the filer has no reports and exits non-zero

### Requirement: Filer resolution for the report listing

The system SHALL resolve the `<filer>` argument to a single filer using the same
contract as `ocpf filer` and `ocpf expenditures`: a raw numeric `cpfId` for any
filer type, or a candidate name matched case-insensitively against the
legislative field for the requested year, never guessing when a name is
ambiguous.

#### Scenario: Numeric cpfId passed directly

- **WHEN** the user passes a value that is a valid numeric cpfId
- **THEN** the system uses that cpfId directly without name matching

#### Scenario: Unique name match

- **WHEN** the name matches exactly one filer in the legislative field for the
  year
- **THEN** the system resolves to that filer's cpfId and lists their reports

#### Scenario: Resolution year does not bound the reports listed

- **WHEN** a filer is resolved by name against one year's legislative field
- **THEN** the listing still covers every year that filer has filed in, so that
  a filing from a year the legislative field does not cover remains reachable

#### Scenario: Ambiguous name match

- **WHEN** the name matches more than one filer in the legislative field
- **THEN** the system prints the matching filers with their cpfIds and offices
  and exits non-zero without guessing

#### Scenario: No name match

- **WHEN** the name matches no filer in the legislative field for the year
- **THEN** the system prints an error indicating no match, notes that a cpfId may
  be passed directly, and exits non-zero

### Requirement: Complete retrieval of the report list

The system SHALL retrieve the filer's complete set of reports, paginating as
needed, and SHALL NOT silently truncate, skip, or duplicate reports. Where the
underlying API's record offset is one-based, the system SHALL page from a
one-based offset.

#### Scenario: Filer with more reports than one page

- **WHEN** the resolved filer has filed more reports than a single API page
  returns
- **THEN** the system requests further pages until the list is exhausted and the
  rendered count equals the number of reports the filer has filed

#### Scenario: No report is dropped or repeated at a page boundary

- **WHEN** the system crosses a page boundary during retrieval
- **THEN** the assembled list contains each report exactly once, with no report
  omitted at the boundary and none repeated

#### Scenario: All report types are included

- **WHEN** the filer has filed reports of several different types, including
  periodic reports, deposit reports, and bank reports
- **THEN** the listing includes reports of every type the filer has filed, not
  only one category

#### Scenario: Reports of every base report type are merged into one listing

- **WHEN** the filer's reports are grouped by the API into several categories
- **THEN** the system retrieves every category and presents them as a single
  merged listing ordered by recency, not as separate per-category listings

### Requirement: Amended filings

The system SHALL show the operative version of each filing by default, excluding
versions that a later amendment has superseded, and SHALL mark a filing that is
itself an amendment. The system SHALL provide a flag that includes superseded
versions in the listing.

#### Scenario: Superseded versions excluded by default

- **WHEN** the filer has amended a previously filed report and no flag is given
- **THEN** the listing includes the operative filing once and omits the
  superseded version

#### Scenario: Amendment is marked

- **WHEN** a listed filing is an amendment of an earlier report
- **THEN** the row marks it as an amendment

#### Scenario: Superseded versions requested

- **WHEN** the user passes the flag that includes superseded filings
- **THEN** the listing includes both the operative filing and the versions it
  superseded, each marked so the two are distinguishable

### Requirement: Per-report period and totals

The system SHALL display, for each listed report, the reporting period the filing
covers and the receipt and expenditure totals reported for that period, formatted
as currency.

#### Scenario: Period and totals shown

- **WHEN** the listing renders in default output
- **THEN** each row shows the reporting period covered by the filing and its
  receipt and expenditure totals as formatted currency

#### Scenario: Totals are per filing, not cumulative

- **WHEN** a filer has filed several reports in one calendar year
- **THEN** each row's totals describe that filing's own reporting period rather
  than a year-to-date cumulative figure

### Requirement: Filtering the report listing

The system SHALL support narrowing the listing by report type and by date, and
SHALL support limiting the number of reports shown.

#### Scenario: Filtering by report type

- **WHEN** the user runs `ocpf reports <filer> --type "pre-election"`
- **THEN** the system lists only reports whose type matches that text,
  case-insensitively, including special-election variants of that type

#### Scenario: Filtering by year

- **WHEN** the user passes `--year 2013`
- **THEN** the system lists only reports whose reporting period falls in that
  year

#### Scenario: Filtering by date range

- **WHEN** the user passes `--since` and/or `--until` with dates
- **THEN** the system lists only reports whose reporting period falls within the
  given bounds

#### Scenario: Limiting the number of reports

- **WHEN** the user passes `--limit <n>`
- **THEN** the system shows at most `n` reports and indicates that the listing was
  limited

#### Scenario: Filter matches no report

- **WHEN** the filer's reports are retrieved successfully but no report matches
  the user's filters
- **THEN** the system reports on standard output that no reports matched,
  naming what was filtered on, and exits with status zero

### Requirement: Link to the filed report

The system SHALL display, or make available in machine-readable output, the
canonical OCPF web link for each listed report, so that the filed document
remains reachable from the command's output.

#### Scenario: Report link available

- **WHEN** the listing renders
- **THEN** the canonical OCPF report link for each report is present in the
  output or reachable from the identifier shown

### Requirement: JSON output of the report listing

The system SHALL support a `--json` flag that emits the report listing as JSON to
standard output and prints no human-formatted output.

#### Scenario: JSON output requested

- **WHEN** the user runs `ocpf reports <filer> --json`
- **THEN** the system emits the resolved filer and the matching reports as valid
  JSON to standard output, including each report's identifier, type, reporting
  period, date filed, totals, and canonical link, and prints no human-formatted
  table

#### Scenario: JSON empty result

- **WHEN** `--json` is requested and the user's filters match no report
- **THEN** the system emits a valid JSON document containing an empty result set
  and exits with status zero
