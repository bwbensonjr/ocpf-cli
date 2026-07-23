## 1. Implement `--version`

- [x] 1.1 Add a helper in `cli.py` that resolves the version via
  `importlib.metadata.version("ocpf")`, catching `PackageNotFoundError` and
  returning `"unknown"`.
- [x] 1.2 Add a `_version_callback(value: bool)` that, when set, prints
  `ocpf <version>` to stdout and raises `typer.Exit()`.
- [x] 1.3 Add an eager `--version` / `-V` option to the `main` callback wired to
  `_version_callback` (`is_eager=True`), so it short-circuits before subcommand
  dispatch and the no-subcommand help path.

## 2. Tests

- [x] 2.1 Test `ocpf --version` (and `-V`): exit code zero and output contains a
  version string (e.g. matches `ocpf ` followed by a non-empty version).
- [x] 2.2 Test that `ocpf --version race` (option before the subcommand) reports
  the version and exits zero without running the race command (no API calls).

## 3. Verification

- [x] 3.1 Run `uv run pytest`; confirm all tests pass.
- [x] 3.2 Run `uv run ocpf --version` and confirm it prints the current version.
