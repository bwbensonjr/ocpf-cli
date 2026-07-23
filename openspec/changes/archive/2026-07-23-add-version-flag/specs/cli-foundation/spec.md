## ADDED Requirements

### Requirement: Version reporting

The system SHALL provide a top-level `--version` option (aliased `-V`) on the
`ocpf` command that prints the installed package version and exits with status
zero. The version SHALL be read from the installed package metadata so that it
matches the published release. The option SHALL be eager: when given at the top
level it takes effect without requiring a subcommand and short-circuits before
any subcommand executes.

#### Scenario: Reporting the version

- **WHEN** the user runs `ocpf --version` (or `ocpf -V`)
- **THEN** the system prints the installed version to standard output and exits
  with status zero, without requiring or running a subcommand

#### Scenario: Version short-circuits subcommand dispatch

- **WHEN** the user runs `ocpf --version <command>` (the option before a
  subcommand name)
- **THEN** the system prints the version and exits zero without executing the
  command

#### Scenario: Version unavailable

- **WHEN** the package metadata cannot be resolved (the distribution is not
  installed)
- **THEN** the system reports the version as `unknown` and exits zero rather than
  raising an error
