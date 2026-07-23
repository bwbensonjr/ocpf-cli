## ADDED Requirements

### Requirement: `ocpf` command entry point

The system SHALL provide an executable command named `ocpf` that acts as the
top-level entry point for all subcommands, runnable via `uv run ocpf ...` and as
an installed console script.

#### Scenario: Invoking with no arguments shows help

- **WHEN** the user runs `ocpf` with no subcommand
- **THEN** the system prints top-level help listing available commands and exits
  with a non-error status

#### Scenario: Requesting help

- **WHEN** the user runs `ocpf --help` or `ocpf <command> --help`
- **THEN** the system prints usage, a description, and available options for that
  scope

#### Scenario: Unknown command

- **WHEN** the user runs `ocpf <unknown-command>`
- **THEN** the system prints an error naming the unknown command and exits with a
  non-zero status

### Requirement: OCPF API client

The system SHALL provide a shared HTTP client for the OCPF REST API that issues
GET requests against the base URL `https://api.ocpf.us/`, parses JSON responses,
applies a request timeout, and raises a typed error on HTTP or network failure.

#### Scenario: Successful request

- **WHEN** the client requests a path that returns HTTP 200 with a JSON body
- **THEN** the client returns the parsed JSON value

#### Scenario: HTTP error status

- **WHEN** the client requests a path that returns a 4xx or 5xx status
- **THEN** the client raises a typed API error carrying the status code and the
  requested path

#### Scenario: Network or timeout failure

- **WHEN** a request cannot complete within the configured timeout or the network
  fails
- **THEN** the client raises a typed API error describing the failure rather than
  leaking a raw library exception

### Requirement: Human-readable output by default

The system SHALL render command results as human-readable text (aligned tables
for lists) by default, sized for a terminal.

#### Scenario: Default rendering of a result set

- **WHEN** a command produces a set of records and no output-format flag is given
- **THEN** the system prints an aligned, labeled table to standard output

### Requirement: Machine-readable JSON output

The system SHALL support a `--json` flag on data-producing commands that emits
the command's result as JSON to standard output, suitable for piping.

#### Scenario: JSON output requested

- **WHEN** the user runs a data-producing command with `--json`
- **THEN** the system prints the result as valid JSON to standard output and
  prints no human-formatted table

#### Scenario: JSON output is pipeable

- **WHEN** `--json` output is piped to another process
- **THEN** standard output contains only the JSON document (human status/progress
  messages, if any, go to standard error)

### Requirement: Errors and exit codes

The system SHALL report errors with a clear, human-readable message on standard
error and exit with a non-zero status; successful commands SHALL exit with status
zero.

#### Scenario: Error is reported clearly

- **WHEN** a command fails (bad input, API error, or no matching data)
- **THEN** the system prints a concise error message to standard error and exits
  non-zero

#### Scenario: Success exit code

- **WHEN** a command completes successfully
- **THEN** the system exits with status zero
