## Purpose

Provide the `ocpf totals` command, which reports how much a single OCPF filer
received or paid between two explicit dates, so that pre-election money can be
measured without the post-election money a published year-to-date figure
includes.

## ADDED Requirements

### Requirement: `ocpf totals` command

The system SHALL provide a command `ocpf totals <filer> --start <date> --end
<date>` that reports the number of records and the total amount for that filer
over the closed window, for one category of money.

#### Scenario: Total over a window

- **WHEN** the user runs `ocpf totals 14902 --start 2024-01-01 --end 2024-10-31`
- **THEN** the system prints the record count and the total amount as formatted
  currency and exits with status zero

#### Scenario: Window crossing a year boundary

- **WHEN** the requested window starts in one calendar year and ends in another
- **THEN** the system reports a single total covering the whole window rather
  than refusing or splitting it by year

#### Scenario: Window containing no records

- **WHEN** the filer has no records of the requested category in the window
- **THEN** the system reports a zero total with a zero count on standard output,
  naming the window, and exits with status zero

### Requirement: Both bounds are required

The system SHALL require both `--start` and `--end`, and SHALL reject an
invocation that supplies neither or only one.

#### Scenario: Missing a bound

- **WHEN** the user supplies `--start` without `--end`, or neither
- **THEN** the system prints an error naming the missing bound and exits
  non-zero, without reporting a total

#### Scenario: Unparseable date

- **WHEN** a bound is not a date the system can parse
- **THEN** the system prints an error naming the offending value and the
  accepted formats, and exits non-zero

#### Scenario: Inverted window

- **WHEN** `--start` is later than `--end`
- **THEN** the system prints an error describing the inverted window and exits
  non-zero rather than reporting a total over an empty range

### Requirement: The window is reported with the figure

The system SHALL include the window the total covers in its output, in both
human-readable and machine-readable form, so that a figure is never presented
without the dates that produced it.

#### Scenario: Window echoed in default output

- **WHEN** the command reports a total
- **THEN** the output states the start and end dates the total covers

#### Scenario: Window present in JSON output

- **WHEN** the command reports a total with `--json`
- **THEN** the emitted document carries the start and end dates alongside the
  count and total

### Requirement: Category selection

The system SHALL support a `--category` option accepting `receipts` or
`expenditures`, defaulting to `receipts`, and SHALL NOT pass the user's string
to the API's record-kind parameter.

#### Scenario: Receipts by default

- **WHEN** the user omits `--category`
- **THEN** the system reports money the filer received

#### Scenario: Expenditures requested

- **WHEN** the user passes `--category expenditures`
- **THEN** the system reports money the filer paid, and labels the figure as
  expenditures

#### Scenario: Unrecognized category is rejected

- **WHEN** the user passes a category the system does not recognize
- **THEN** the system prints an error naming the valid categories and exits
  non-zero, rather than passing the value through to the API

#### Scenario: Money received is never reported as money paid

- **WHEN** the API returns records of a different kind than the category
  requested
- **THEN** the system fails with an error rather than displaying the figure

### Requirement: Single-request retrieval with a verified filter

The system SHALL obtain the count and total from the API's own summary of the
filtered set rather than by retrieving and summing individual records, and SHALL
verify that the date bounds were actually applied before reporting the figure.

#### Scenario: Total comes from the API summary

- **WHEN** the command reports a total
- **THEN** it issues a single request for the filtered summary rather than
  paging the filer's full record set

#### Scenario: Ignored date bound is detected

- **WHEN** the API returns a record dated outside the requested window,
  indicating the date bounds were not applied
- **THEN** the system fails with an error rather than reporting a total that
  covers more than the window it names

#### Scenario: Summary missing from the response

- **WHEN** the API response carries no summary
- **THEN** the system fails with an error rather than reporting a zero or
  partial total

### Requirement: Filer resolution for totals

The system SHALL resolve the `<filer>` argument to a single filer using the same
contract as `ocpf filer`: a raw numeric `cpfId` for any filer type, or a
candidate name matched case-insensitively against the legislative field, never
guessing when a name is ambiguous.

#### Scenario: Numeric cpfId passed directly

- **WHEN** the user passes a value that is a valid numeric cpfId
- **THEN** the system uses that cpfId directly without name matching

#### Scenario: Ambiguous name match

- **WHEN** the name matches more than one legislative filer
- **THEN** the system prints the matching filers with their cpfIds and offices
  and exits non-zero without guessing

#### Scenario: No name match

- **WHEN** the name matches no filer in the legislative field
- **THEN** the system prints an error indicating no match, notes that a cpfId may
  be passed directly, and exits non-zero

### Requirement: JSON output of a total

The system SHALL support a `--json` flag that emits the result as JSON to
standard output and prints no human-formatted output.

#### Scenario: JSON output requested

- **WHEN** the user runs `ocpf totals <filer> --start <date> --end <date> --json`
- **THEN** the system emits the resolved cpfId, the category, the window, the
  record count and the numeric total as valid JSON to standard output, and
  prints no human-formatted text
