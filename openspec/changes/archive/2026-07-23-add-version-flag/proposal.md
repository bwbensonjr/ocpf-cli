## Why

There is no way to ask the installed CLI what version it is. Users filing bug
reports, and scripts checking compatibility, need `ocpf --version`. The package
version is already the single source of truth (tag-driven via `hatch-vcs`); the
CLI just needs to surface it.

## What Changes

- Add a top-level `--version` (with `-V` alias) option to the `ocpf` command. It
  prints the installed package version and exits with status zero.
- The version string is read at runtime from the installed package metadata
  (`importlib.metadata.version("ocpf")`) so it always matches the published
  release; no version literal is duplicated in the source.
- `--version` is eager: it works with no subcommand and takes precedence over
  subcommand parsing (`ocpf --version` and `ocpf race --version` both report the
  version without running a command).

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `cli-foundation`: the `ocpf` command entry point gains a `--version` option
  that reports the installed version and exits zero.

## Impact

- Code: `src/ocpf_cli/cli.py` (add the eager `--version` option and a small
  helper to resolve the version from package metadata).
- Tests: `tests/test_cli.py` (assert `--version` prints a version and exits
  zero).
- No new dependencies (`importlib.metadata` is in the standard library).
- No change to existing command behavior or output.
