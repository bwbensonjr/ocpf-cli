## Purpose

Provide the `ocpf report` command, which renders a single filed OCPF campaign
finance report — the same filing the OCPF web UI shows at its DisplayReport page
— including its header, its reporting period, its schedule totals, and, on
request, the individual line items of any schedule.

## ADDED Requirements

### Requirement: `ocpf report` command

The system SHALL provide a command `ocpf report <report-id>` that retrieves and
renders a single filed report identified by its numeric report id.

#### Scenario: Report rendered by id

- **WHEN** the user runs `ocpf report 170378`
- **THEN** the system prints that report's header, reporting period, and schedule
  totals and exits with status zero

#### Scenario: Non-numeric report id

- **WHEN** the user passes a report id that is not a number
- **THEN** the system prints an error naming the invalid argument and exits
  non-zero

### Requirement: Report header

The system SHALL display the filing's identifying header, including the report
type as OCPF names it, the reporting period the filing covers, the date filed,
the committee name, the candidate name, and the office and district sought where
the filing records them.

#### Scenario: Header of a candidate report

- **WHEN** the report renders in default output for a candidate committee filing
- **THEN** the header shows the report type, the reporting period, the date
  filed, the committee name, the candidate name, and the office and district
  sought

#### Scenario: Special-election report type is named

- **WHEN** the report is a pre-election or post-election report filed for a
  special election
- **THEN** the header names that report type as OCPF describes it, distinguishing
  it from the regular pre-election or post-election report

### Requirement: Schedule totals

The system SHALL display the filing's reported totals, including the starting
balance, itemized and unitemized receipts, itemized and unitemized expenditures,
in-kind contributions, liabilities, and the ending balance, formatted as
currency.

#### Scenario: Totals shown

- **WHEN** the report renders in default output
- **THEN** the system shows the starting balance, receipt totals, expenditure
  totals, in-kind total, liability total, and ending balance as formatted
  currency

#### Scenario: Totals are for the filing's own period

- **WHEN** the report covers a reporting period shorter than a calendar year,
  such as a special election window
- **THEN** the totals shown describe that reporting period rather than a
  year-to-date cumulative figure

### Requirement: Schedule line items

The system SHALL support displaying the individual line items recorded in the
filing's schedules — receipts, expenditures, out-of-pocket expenditures, in-kind
contributions, liabilities, and subvendor payments — on request, and SHALL NOT
print them by default.

#### Scenario: Line items omitted by default

- **WHEN** the user runs `ocpf report <report-id>` with no schedule requested
- **THEN** the system prints the header and totals without the individual line
  items

#### Scenario: A schedule requested

- **WHEN** the user requests a named schedule, such as `--schedule expenditures`
- **THEN** the system prints that schedule's line items, each showing at minimum
  the date, the amount, the counterparty name, and the record type

#### Scenario: Several schedules requested

- **WHEN** the user requests more than one schedule
- **THEN** the system prints each requested schedule as its own labeled section

#### Scenario: Requested schedule is empty

- **WHEN** the user requests a schedule the filing records no items for
- **THEN** the system reports that the schedule is empty rather than printing an
  empty table, and exits with status zero

#### Scenario: Unknown schedule name

- **WHEN** the user requests a schedule name the system does not recognize
- **THEN** the system prints an error naming the valid schedule names and exits
  non-zero

### Requirement: Amendment lineage

The system SHALL indicate whether the filing is an amendment and whether it has
itself been amended, and SHALL identify the related filing when the report
records one.

#### Scenario: Report is an amendment

- **WHEN** the filing is an amendment of an earlier report
- **THEN** the system marks it as an amendment and names the report id it amends

#### Scenario: Report has been superseded

- **WHEN** a later amendment of the filing exists
- **THEN** the system indicates that the filing has been amended and names the
  superseding report id

#### Scenario: Original, unamended report

- **WHEN** the filing is neither an amendment nor amended
- **THEN** the system prints no amendment marker

### Requirement: Link to the filed report

The system SHALL display the canonical OCPF web link for the filing, so that the
filed document, including its PDF, remains reachable from the command's output.

#### Scenario: Link shown

- **WHEN** the report renders in default output
- **THEN** the system prints the canonical OCPF web link for that report

### Requirement: Unknown or invalid report id

The system SHALL report a report id that identifies no filing as a clear
not-found error, regardless of the HTTP status the underlying API uses to signal
it, and SHALL NOT present it as a server fault.

#### Scenario: Report id below the valid range

- **WHEN** the user passes a numeric report id the API rejects as out of range
- **THEN** the system reports that no such report exists and exits non-zero

#### Scenario: Well-formed report id that does not exist

- **WHEN** the user passes a well-formed report id for which the API returns a
  server error rather than a not-found status
- **THEN** the system reports that no such report exists and exits non-zero,
  without implying an OCPF outage

#### Scenario: Genuine API failure

- **WHEN** the API is unreachable or times out
- **THEN** the system reports the failure as an API error, distinctly from a
  not-found report, and exits non-zero

### Requirement: JSON output of a report

The system SHALL support a `--json` flag that emits the report as JSON to
standard output and prints no human-formatted output.

#### Scenario: JSON output requested

- **WHEN** the user runs `ocpf report <report-id> --json`
- **THEN** the system emits the report's header, reporting period, totals,
  amendment lineage, and canonical link as valid JSON to standard output and
  prints no human-formatted table

#### Scenario: JSON includes requested schedules

- **WHEN** `--json` is combined with one or more requested schedules
- **THEN** the emitted JSON includes the line items of each requested schedule
