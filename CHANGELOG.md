# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-23

### Added

- `ocpf --version` (and `-V`) prints the installed version and exits.

### Changed

- CI/release workflows: bumped GitHub Actions off Node 20 to current majors
  (`checkout` v7, `setup-uv` v9, `upload-artifact` v7, `download-artifact` v8).

## [0.1.0] - 2026-07-23

Initial release. Published to PyPI as [`ocpf`](https://pypi.org/project/ocpf/) —
installable and runnable with `uvx ocpf`, `pipx install ocpf`, or
`pip install ocpf`.

### Added

- `ocpf race <district> [--year] [--json]` — year-to-date financial summary of
  the legislative (House/Senate) candidates in a district: receipts,
  expenditures, and cash on hand, with primary/general election dates and the
  as-of reporting date as timeline context.
- `ocpf filer <filer> [--year] [--json]` — a single filer's committee profile,
  cumulative year-to-date finances, and most recent reports.
- District resolution by case-insensitive name (with `&`/`and` treated alike) or
  by raw numeric code; ambiguous names are listed rather than guessed.
- Historical race support: for pre-2020 cycles, where the current legislative
  feeds carry no money, `ocpf race` falls back to the district-scoped
  `onballot/finsummaries` endpoint, rendering final full-cycle totals
  (`Raised` / `Spent` / `End Bal`) with a winner (`W`) marker.
- `--json` output for both commands, emitting the underlying records (including
  numeric monetary values) to stdout while human status goes to stderr.

### Packaging

- MIT licensed; metadata, keywords, and classifiers for Python 3.11–3.13.
- Tag-driven versioning via `hatch-vcs`.
- Automated, test-gated release to PyPI via GitHub Actions using Trusted
  Publishing (OIDC), with CI running the test suite on Python 3.11–3.13.

[Unreleased]: https://github.com/bwbensonjr/ocpf-cli/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/bwbensonjr/ocpf-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bwbensonjr/ocpf-cli/releases/tag/v0.1.0
