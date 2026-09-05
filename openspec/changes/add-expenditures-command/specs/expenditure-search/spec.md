## Purpose

Provide the `ocpf expenditures` command, which lists and totals the payments a
single OCPF filer has made: retrieving their expenditure records in full,
filtering them by date, payee, and amount, and rendering them either itemized or
rolled up by payee, with optional JSON output.

## ADDED Requirements

### Requirement: `ocpf expenditures` command

The system SHALL provide a command `ocpf expenditures <filer>` that lists the
expenditure records a single OCPF filer has reported, together with the total
amount and the number of records shown.

#### Scenario: Expenditures listed for a filer

- **WHEN** the user runs `ocpf expenditures 17436`
- **THEN** the system prints that filer's expenditure records, each showing at
  minimum the date, amount, payee, and purpose, followed by the total amount and
  the record count

#### Scenario: Filer has no expenditure records at all

- **WHEN** the resolved filer has reported no expenditures of any kind
- **THEN** the system reports that the filer has no expenditure records and exits
  non-zero

### Requirement: Filer resolution for expenditures

The system SHALL resolve the `<filer>` argument to a single filer using the same
contract as `ocpf filer`: a raw numeric `cpfId` for any filer type, or a
candidate name matched case-insensitively against the legislative field for the
requested year, never guessing when a name is ambiguous.

#### Scenario: Numeric cpfId passed directly

- **WHEN** the user passes a value that is a valid numeric cpfId
- **THEN** the system uses that cpfId directly without name matching

#### Scenario: Unique name match

- **WHEN** the name matches exactly one filer in the legislative field for the
  year
- **THEN** the system resolves to that filer's cpfId and lists their expenditures

#### Scenario: Ambiguous name match

- **WHEN** the name matches more than one filer in the legislative field
- **THEN** the system prints the matching filers with their cpfIds and offices
  and exits non-zero without guessing

#### Scenario: No name match

- **WHEN** the name matches no filer in the legislative field for the year
- **THEN** the system prints an error indicating no match, notes that a cpfId may
  be passed directly, and exits non-zero

### Requirement: Complete retrieval of expenditure records

The system SHALL retrieve every expenditure record matching the request, not
only the first page returned by the OCPF API, and SHALL NOT silently truncate a
result set. When the number of records retrieved does not match the count the
API reports for the same query, the system SHALL treat this as an error rather
than reporting a partial total as if it were complete.

#### Scenario: Result set spans multiple pages

- **WHEN** a filer has more expenditure records than fit in a single API response
- **THEN** the system retrieves all of them and the reported total and record
  count reflect the complete set

#### Scenario: Retrieval is incomplete

- **WHEN** the number of records retrieved is fewer than the count the API
  reports for that query
- **THEN** the system reports the discrepancy as an error and exits non-zero
  rather than printing a total that understates the true figure

#### Scenario: Expenditures are not confused with receipts

- **WHEN** the command retrieves records for any filer
- **THEN** every record returned is an expenditure, and the system SHALL fail
  rather than display money the filer received as money the filer paid

### Requirement: Filtering expenditures

The system SHALL support narrowing the expenditure list by calendar year
(`--year`), by date range (`--since`, `--until`), by payee text (`--vendor`,
matched case-insensitively as a substring), and by amount bounds
(`--min-amount`, `--max-amount`). Filters SHALL combine conjunctively, and the
displayed total and record count SHALL describe the filtered set.

#### Scenario: Filter by year

- **WHEN** the user runs `ocpf expenditures <filer> --year 2026`
- **THEN** only expenditures dated in 2026 are listed, and the total reflects
  only those records

#### Scenario: Filter by payee

- **WHEN** the user runs `ocpf expenditures <filer> --vendor "consulting"`
- **THEN** only expenditures whose payee contains that text, matched without
  regard to case, are listed

#### Scenario: Filter by amount

- **WHEN** the user passes `--min-amount 1000`
- **THEN** only expenditures of at least that amount are listed

#### Scenario: Filters combine

- **WHEN** the user passes both `--year 2026` and `--vendor "printing"`
- **THEN** only records satisfying both conditions are listed

### Requirement: Empty filtered result is a successful finding

When the filer resolves and their expenditure records are retrieved
successfully, but a user-supplied filter matches none of them, the system SHALL
report the empty result on standard output, state what was searched, and exit
with status zero. An absence of matching payments is an answer, not a failure.

#### Scenario: Vendor filter matches nothing

- **WHEN** the user runs `ocpf expenditures <filer> --vendor "Connection Strategies"`
  and the filer has expenditure records but none to that payee
- **THEN** the system prints that no expenditures matched, names the filter that
  was applied, and exits with status zero

#### Scenario: Empty result states the search scope

- **WHEN** a filter matches no records
- **THEN** the message indicates how many records were searched and the date
  range they span, so the user can distinguish "no such payment" from "no data
  for this period"

#### Scenario: Empty filtered result in JSON

- **WHEN** a filter matches no records and `--json` is passed
- **THEN** the system emits valid JSON containing an empty record list and a
  zero total, and exits with status zero

### Requirement: Vendor rollup view

The system SHALL support a `--by-vendor` flag that, instead of the itemized
list, groups the filtered expenditures by payee and displays each payee's total
amount and record count, ordered by total amount descending.

#### Scenario: Rollup requested

- **WHEN** the user runs `ocpf expenditures <filer> --year 2026 --by-vendor`
- **THEN** the system prints one row per payee with that payee's total and record
  count, largest total first

#### Scenario: Rollup respects filters

- **WHEN** `--by-vendor` is combined with any filter
- **THEN** the grouped totals reflect only the records matching that filter

#### Scenario: Rollup total agrees with itemized total

- **WHEN** the same query is run with and without `--by-vendor`
- **THEN** the sum of the grouped totals equals the itemized total

### Requirement: Record provenance and payee fidelity

Each expenditure SHALL be attributable to the OCPF report that disclosed it, and
the system SHALL distinguish records the committee itemized from records derived
from bank statements, whose payee may be an opaque bank description rather than
the true recipient.

#### Scenario: Source report available

- **WHEN** expenditure records are emitted as JSON
- **THEN** each record includes an identifier for, or link to, the OCPF report it
  came from

#### Scenario: Bank-reported entries are distinguishable

- **WHEN** the listing includes records derived from bank statements
- **THEN** the system marks them as such, so the user can tell a disclosed payee
  from an undisclosed one

#### Scenario: OCPF's clarified payee is honored

- **WHEN** a record carries a payee clarification supplied by OCPF that differs
  from the payee string as filed
- **THEN** the system treats the clarified name as the recipient, so a payment
  whose filed payee is an opaque bank description is attributed to the recipient
  OCPF identified

#### Scenario: The filed payee string remains recoverable

- **WHEN** a clarified payee is displayed in place of the string as filed
- **THEN** the system also shows the filed string, and indicates that clarified
  payees are being displayed, so the substitution is never silent

#### Scenario: No merge is inferred beyond OCPF's own

- **WHEN** two payee strings resemble each other but OCPF has clarified neither
- **THEN** the system keeps them as separate payees rather than merging them
  under a guessed canonical name

#### Scenario: A grouped payee discloses what it absorbed

- **WHEN** a rollup group covers more than one filed payee spelling
- **THEN** the system indicates how many filed spellings the group covers, and
  the machine-readable output lists them

### Requirement: Limiting displayed records

The system SHALL support a `--limit <n>` flag that caps the number of rows
displayed. When a limit elides records, the system SHALL indicate that the
display is truncated, and the reported total SHALL continue to describe the full
filtered set rather than only the displayed rows.

#### Scenario: Limit applied

- **WHEN** the user passes `--limit 10` and more than ten records match
- **THEN** the system displays ten rows and indicates that further records were
  not shown

#### Scenario: Total is unaffected by the limit

- **WHEN** a limit elides records
- **THEN** the reported total amount and record count describe every record
  matching the filters, not only the displayed rows

### Requirement: JSON output of expenditures

The system SHALL support a `--json` flag that emits the filtered expenditures to
standard output as JSON, including numeric monetary values alongside any
formatted ones, and printing no human-formatted table.

#### Scenario: JSON output requested

- **WHEN** the user runs `ocpf expenditures <filer> --json`
- **THEN** the system emits the matching expenditure records and the summary
  total as valid JSON to standard output, including numeric monetary values, and
  prints no human-formatted table

#### Scenario: JSON reflects the selected view

- **WHEN** `--json` is combined with `--by-vendor`
- **THEN** the emitted JSON contains the grouped payee totals rather than the
  itemized records
