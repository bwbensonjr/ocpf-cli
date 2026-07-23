# filer-lookup Specification

## Purpose

Provide the `ocpf filer` command, which produces a filing summary for a single
OCPF filer: resolving the filer from a numeric cpfId or a legislative name match,
then rendering their profile, cumulative year-to-date finances, and most recent
reports, with optional JSON output.

## Requirements

### Requirement: `ocpf filer` command

The system SHALL provide a command `ocpf filer <filer> [--year <year>]` that
produces a filing summary for a single OCPF filer: their profile, cumulative
year-to-date finances, and their most recent reports.

#### Scenario: Summary by cpfId

- **WHEN** the user runs `ocpf filer 14454`
- **THEN** the system prints that filer's profile, year-to-date finances, and
  recent filing log

#### Scenario: Default year

- **WHEN** the user omits `--year`
- **THEN** the system uses the current calendar year for any name resolution and
  year-to-date context

#### Scenario: Explicit year

- **WHEN** the user passes `--year 2026`
- **THEN** the system resolves names against the 2026 legislative field and
  reports the year-to-date context for that year

### Requirement: Filer resolution

The system SHALL resolve the `<filer>` argument to a single filer. It SHALL
accept a raw numeric `cpfId` for any filer type, or a candidate name matched
case-insensitively against the legislative field for the requested year, and it
SHALL NOT guess when a name is ambiguous.

#### Scenario: Numeric cpfId passed directly

- **WHEN** the user passes a value that is a valid numeric cpfId
- **THEN** the system uses that cpfId directly without name matching

#### Scenario: Unique name match

- **WHEN** the name matches exactly one filer in the legislative field for the
  year
- **THEN** the system resolves to that filer's cpfId and proceeds

#### Scenario: Ambiguous name match

- **WHEN** the name matches more than one filer in the legislative field
- **THEN** the system prints the matching filers with their cpfIds and offices
  and exits without guessing

#### Scenario: No name match

- **WHEN** the name matches no filer in the legislative field for the year
- **THEN** the system prints an error indicating no match, notes that a cpfId may
  be passed directly, and exits non-zero

#### Scenario: Unknown cpfId

- **WHEN** the resolved cpfId corresponds to no filer
- **THEN** the system reports that no filer was found for that cpfId and exits
  non-zero

### Requirement: Filer profile

The system SHALL display the filer's identifying profile, including committee
name, candidate name, party, office sought and/or held, active/closed status,
and organization date, drawn from the OCPF filer record.

#### Scenario: Profile of an active candidate committee

- **WHEN** the summary renders in default output for an active filer
- **THEN** the header shows the committee name, candidate name, party, office,
  an active status, and the organization date

#### Scenario: Closed committee is marked

- **WHEN** the filer's committee is closed
- **THEN** the profile indicates the closed status (and closed date when present)

### Requirement: Year-to-date finances

The system SHALL display the filer's cumulative year-to-date receipts,
expenditures, and current cash on hand as formatted currency, together with the
as-of reporting date, and SHALL NOT segment the money by election.

#### Scenario: YTD figures shown

- **WHEN** the summary renders in default output and the filer has a
  year-to-date record
- **THEN** the system shows cumulative receipts, expenditures, and cash on hand
  as formatted currency with the as-of reporting date

#### Scenario: Money is not segmented by election

- **WHEN** the filer's year is one with both a primary and a general election
- **THEN** the receipts, expenditures, and cash on hand are shown as a single
  cumulative year-to-date figure, not divided into primary and general amounts

### Requirement: Recent filing log

The system SHALL display the filer's most recent reports, each showing at
minimum the report type, reporting period, date filed, and receipt and
expenditure totals.

#### Scenario: Recent reports listed

- **WHEN** the summary renders in default output and the filer has filed reports
- **THEN** the system prints a table of the most recent reports with report type,
  reporting period, date filed, receipts, and expenditures

#### Scenario: No reports filed

- **WHEN** the filer has filed no reports
- **THEN** the system indicates that no reports were found rather than printing
  an empty table

### Requirement: JSON output of the filer summary

The system SHALL support a `--json` flag that emits the filer summary as JSON to
standard output, including the underlying numeric monetary values, and prints no
human-formatted output.

#### Scenario: JSON output requested

- **WHEN** the user runs `ocpf filer <filer> --json`
- **THEN** the system emits the filer profile, year-to-date record, and recent
  reports as valid JSON to standard output, including numeric monetary values,
  and prints no human-formatted table
