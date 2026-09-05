## MODIFIED Requirements

### Requirement: Errors and exit codes

The system SHALL report errors with a clear, human-readable message on standard
error and exit with a non-zero status; successful commands SHALL exit with status
zero.

A successfully retrieved result set that a user-supplied filter narrows to
nothing SHALL NOT be treated as an error: the system SHALL report the empty
result on standard output and exit zero. Failure to accept the input, retrieve
the data, or resolve what the user named remains an error.

#### Scenario: Error is reported clearly

- **WHEN** a command fails (bad input, API error, or data that cannot be
  retrieved or resolved)
- **THEN** the system prints a concise error message to standard error and exits
  non-zero

#### Scenario: Success exit code

- **WHEN** a command completes successfully
- **THEN** the system exits with status zero

#### Scenario: Unresolvable input is an error

- **WHEN** the user names something the system cannot resolve to any record, such
  as an unknown district or a candidate name matching no filer
- **THEN** the system reports the failure on standard error and exits non-zero

#### Scenario: Filter matching nothing is a successful empty result

- **WHEN** a command retrieves a result set successfully and a user-supplied
  filter matches none of its records
- **THEN** the system reports the empty result on standard output, indicating
  what was searched, and exits with status zero
