## 1. Distribution metadata and license

- [x] 1.1 Add `LICENSE` at the repo root: MIT text, copyright "Brent Benson".
- [x] 1.2 In `pyproject.toml`, rename `project.name` to `ocpf`.
- [x] 1.3 Add `authors`, `license` (MIT), and `keywords` to `[project]`.
- [x] 1.4 Add `[project.urls]` — Homepage, Repository, and Issues pointing at
  `https://github.com/bwbensonjr/ocpf-cli`.
- [x] 1.5 Add `classifiers`: Python 3.11/3.12/3.13, `Environment :: Console`,
  `License :: OSI Approved :: MIT License`, and a relevant `Topic` /
  `Intended Audience`.

## 2. Tag-driven versioning

- [x] 2.1 Add `hatch-vcs` to `build-system.requires`.
- [x] 2.2 Replace the static `version = "0.1.0"` with `dynamic = ["version"]` and
  add `[tool.hatch.version] source = "vcs"`.
- [x] 2.3 Verify a local build derives the version from git: from a clean tree,
  `uv build` and confirm the artifact version reflects the tag/dev state.

## 3. CI workflow

- [x] 3.1 Add `.github/workflows/ci.yml`: trigger on push and pull_request;
  matrix over Python 3.11, 3.12, 3.13; set up `uv`; `uv sync --extra dev`;
  `uv run pytest`.

## 4. Release workflow (Trusted Publishing)

- [x] 4.1 Add `.github/workflows/release.yml`: trigger on `push` tags `v*`.
- [x] 4.2 Run the test suite as a gate before building.
- [x] 4.3 Build with `uv build` (sdist + wheel) and validate the artifact
  metadata before upload.
- [x] 4.4 Publish via PyPI Trusted Publishing (OIDC): job `permissions:
  id-token: write`, a `pypi` GitHub Environment, and
  `pypa/gh-action-pypi-publish` (or `uv publish` configured for OIDC) — no stored
  API token.

## 5. Docs — README revamp (PyPI-first)

- [x] 5.1 Restructure `README.md` to lead with an **Install** section that
  features `uvx ocpf race ...` first, then `pipx install ocpf` and
  `pip install ocpf`; keep the intro to a concise one-liner above it.
- [x] 5.2 Ensure the **Usage** examples (`ocpf race`, `ocpf filer`, `--json`,
  `--year`) follow Install and read against the installed `ocpf` command.
- [x] 5.3 Move the from-source instructions (`uv sync`, `uv sync --extra dev`,
  `uv run ocpf`) into a **Development** section below Usage, no longer the
  opening.
- [x] 5.4 Add a **Releasing** section documenting the tag-driven flow
  (`git tag vX.Y.Z && git push --tags`).
- [x] 5.5 Document the one-time PyPI **pending Trusted Publisher** registration
  (project `ocpf`, owner `bwbensonjr`, repo `ocpf-cli`, workflow `release.yml`,
  environment `pypi`) as a prerequisite for the first release.

## 6. Verification

- [x] 6.1 Run `uv run pytest` locally; confirm all tests pass.
- [x] 6.2 Run `uv build` locally and confirm sdist + wheel are produced with the
  new name `ocpf`, dynamic version, and included `LICENSE`.
- [x] 6.3 (Maintainer, external) Register the pending Trusted Publisher on PyPI.
- [x] 6.4 (Maintainer, external) Optionally do a TestPyPI dry run, then push
  `v0.1.0` and confirm `uvx ocpf --help` works from the published package.
  (Went straight to PyPI; `ocpf` 0.1.0 published and verified via
  `uvx ocpf@0.1.0 race --year 2008 37th`.)
