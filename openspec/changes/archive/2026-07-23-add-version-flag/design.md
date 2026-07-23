## Context

`ocpf` is a Typer app whose root callback (`main` in `cli.py`) runs with
`invoke_without_command=True` and prints help when no subcommand is given. The
package version is dynamic (`hatch-vcs`), so there is no version literal in the
source to print. Adding `--version` is a small, self-contained change to the
callback.

## Goals / Non-Goals

**Goals:**
- `ocpf --version` prints the version and exits zero, with no subcommand needed.
- The reported version always matches the installed/published package.
- No duplicated version literal to drift from the tag.

**Non-Goals:**
- No `--version` output format beyond a simple, stable line.
- No change to any subcommand's behavior or to the no-args help behavior.

## Decisions

### Resolve the version from installed metadata

Read the version with `importlib.metadata.version("ocpf")` at call time, inside a
small helper.

- **Why:** the build has no static version (hatch-vcs); package metadata is the
  runtime source of truth and matches the published wheel.
- **Alternative — import a `__version__` constant:** would require generating a
  version file at build time and reintroduces drift risk. Rejected.
- **Fallback:** if the distribution is not installed (e.g. running the module
  from a raw source tree with no metadata), `PackageNotFoundError` is caught and
  the version is reported as `"unknown"` rather than crashing.

### Eager `--version` option on the root callback

Add `version: bool = typer.Option(None, "--version", "-V", is_eager=True,
callback=...)` to `main`. The callback prints `ocpf <version>` and raises
`typer.Exit()` when the flag is set.

- **Why eager:** it must short-circuit before subcommand dispatch and before the
  no-subcommand help path, so `ocpf --version` (and `ocpf --version race`) report
  the version without running a command.
- **Placement:** `--version` is a top-level (group) option, so it must precede
  any subcommand. `ocpf race --version` is a Click usage error (exit 2), because
  once parsing reaches the subcommand the flag is matched against `race`, which
  does not define it. This matches the common convention (`git --version`, not
  `git log --version`); we do not add a per-subcommand `--version`.
- **Output shape:** `ocpf <version>` (program name + version) — a common,
  greppable convention. Written to stdout; exit code zero.

## Risks / Trade-offs

- **[Metadata lookup returns a dev version in local editable installs]** →
  Expected and acceptable: `uvx`/`pip` installs report the release version;
  editable dev trees report the hatch-vcs dev version, which is accurate.
- **[`PackageNotFoundError` in an uninstalled source run]** → Handled by the
  `"unknown"` fallback; no crash.

## Open Questions

None.
