## Why

`ocpf` currently only runs from a clone of the repo (`uv run ocpf ...`). To make
it usable by anyone — "no install, just run it" — it needs to be published to
PyPI. Both `ocpf` and `ocpf-cli` are available on PyPI, so we can claim the short
name and ship a clean install/run experience.

## What Changes

- **BREAKING** (distribution only): rename the PyPI distribution to `ocpf` (the
  repo stays `ocpf-cli`; the `ocpf` command is unchanged). This makes
  `uvx ocpf race ...`, `pipx install ocpf`, and `pip install ocpf` work directly.
- Complete the packaging metadata in `pyproject.toml`: `authors`, `license`
  (MIT), `project.urls` (Homepage / Repository / Issues), `classifiers`
  (Python 3.11–3.13, `Environment :: Console`, license, topic), and `keywords`.
- Switch to tag-driven versioning with `hatch-vcs`: `dynamic = ["version"]`, so
  the git tag is the single source of truth for the package version.
- Add a `LICENSE` file (MIT, © Brent Benson).
- Add GitHub Actions:
  - **CI** — run `pytest` on push/PR across Python 3.11, 3.12, 3.13.
  - **Release** — on a `v*` tag: run tests, `uv build`, and publish to PyPI via
    Trusted Publishing (OIDC), with no stored API token.
- Revamp `README.md` to lead with the published tool: an **Install** section
  featuring `uvx ocpf ...` first, then `pipx`/`pip`; usage examples next; the
  from-source `uv sync`/`uv run` instructions demoted into a **Development**
  section; and a short **Releasing** section describing the tag-driven flow.
- Document the one-time PyPI Trusted Publisher setup (pending-publisher flow for
  a brand-new project) so the first tagged release does not fail.

## Capabilities

### New Capabilities
- `packaging`: how the tool is packaged, versioned, distributed, and released —
  PyPI installability under the `ocpf` name, required distribution metadata,
  tag-driven versioning, and automated test-gated publishing via Trusted
  Publishing.

### Modified Capabilities
<!-- None. Command behavior (cli-foundation, race-summary, filer-lookup) is unchanged. -->

## Impact

- Files: `pyproject.toml` (name, metadata, dynamic version, build backend deps),
  new `LICENSE`, new `.github/workflows/ci.yml` and
  `.github/workflows/release.yml`, `README.md`.
- Dependencies: adds `hatch-vcs` to the build-system requires (build-time only;
  no new runtime dependency).
- External, one-time (outside the repo, requires the maintainer): register the
  PyPI Trusted Publisher for project `ocpf` → repo `bwbensonjr/ocpf-cli`,
  workflow `release.yml`.
- No change to runtime behavior, the `ocpf` command name, or the public API.
