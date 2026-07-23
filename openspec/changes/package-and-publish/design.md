## Context

`ocpf-cli` already builds with hatchling (src layout, wheel target) and exposes
the `ocpf` console script. It has never been published: there is no LICENSE, the
distribution metadata is minimal, the version is hardcoded, and there is no CI or
release automation. The goal is a public PyPI package installable/runnable with a
single command, released safely and repeatably.

Decisions settled during exploration: distribution name `ocpf` (both `ocpf` and
`ocpf-cli` were free on PyPI), Trusted Publishing via GitHub Actions, MIT license,
and tag-driven versioning with `hatch-vcs`.

## Goals / Non-Goals

**Goals:**
- `uvx ocpf race ...`, `pipx install ocpf`, and `pip install ocpf` all work.
- Releases are "push a tag": tests gate the build, publish needs no stored token.
- The package version always matches the release tag (no drift).
- The PyPI page has complete, correct metadata.

**Non-Goals:**
- No change to command behavior, the `ocpf` command name, or the public API.
- No new runtime dependencies.
- No automated changelog/release-notes generation (can come later).
- No conda/Homebrew distribution.

## Decisions

### Distribution name `ocpf`, repo stays `ocpf-cli`

Set `project.name = "ocpf"`. The console script is already `ocpf`, so command ==
package, which is what lets `uvx ocpf` resolve without `--from`.

- **Why:** `uvx <tool>` is the most attractive way to hand the tool to someone;
  with a mismatched dist name it degrades to `uvx --from ocpf-cli ocpf`.
- **Alternative — keep `ocpf-cli`:** rejected; forces the `--from` form for the
  zero-install path with no offsetting benefit now that `ocpf` is available.
- The GitHub repo name is left as `ocpf-cli` to avoid churn on remotes/links.

### Tag-driven version via `hatch-vcs`

Use `dynamic = ["version"]`, add `hatch-vcs` to `build-system.requires`, and
configure `[tool.hatch.version] source = "vcs"`. The git tag (`vX.Y.Z`) becomes
the built version.

- **Why:** single source of truth; the tag that triggers the release *is* the
  version, so a release can never publish a mismatched number.
- **Alternative — manual `version =` bump:** simpler but needs two edits kept in
  sync (pyproject + tag) and silently allows drift. Rejected.
- **Consequence:** local dev builds between tags get a dev version like
  `0.1.1.devN+g<sha>`; acceptable. `.git` must be present at build time (it is,
  in CI checkout).

### Two workflows: CI gate + tag-triggered release

`ci.yml` runs on push/PR: matrix over Python 3.11/3.12/3.13, `uv sync --extra
dev`, `uv run pytest`. `release.yml` runs on `push: tags: ['v*']`: run tests,
`uv build`, then publish.

- **Why separate:** CI protects every change; release runs only on tags and
  reuses the same test step as a gate before publishing.

### Trusted Publishing (OIDC), not an API token

`release.yml` publishes with PyPI Trusted Publishing: the job requests an OIDC
token (`permissions: id-token: write`) and uploads via
`pypa/gh-action-pypi-publish` (or `uv publish` configured for OIDC). No secret is
stored in the repo.

- **Why:** no long-lived token to leak or rotate; the trust is scoped to a
  specific repo + workflow + environment.
- **Alternative — `PYPI_API_TOKEN` secret:** simpler to grasp but a standing
  credential and broader blast radius. Rejected.
- **Environment:** use a GitHub Environment named `pypi` on the publish job so
  the Trusted Publisher can be pinned to it (matches PyPI's recommended setup).

### README revamp: lead with the published tool

The README is restructured so an end user meets the published CLI first, not the
developer workflow. The opening becomes an **Install** section that features the
zero-install `uvx ocpf race ...` path first, then `pipx install ocpf` and
`pip install ocpf`. Usage examples follow. The current from-source instructions
(`uv sync`, `uv run ocpf`) are demoted into a **Development** section, and a
**Releasing** section documents the tag-driven flow.

- **Why:** the README today opens with "managed with `uv` … from a clone of this
  repository", which is developer-first and buries the reason to publish. Once the
  tool is on PyPI, the primary audience is people who want to *run* it.
- **Alternative — additive edit** (append PyPI paths, keep the clone-first
  opening): rejected; it leaves the developer framing in the lead and undercuts
  the point of publishing.

### First-release bootstrapping (pending publisher)

A Trusted Publisher normally references an existing PyPI project, but `ocpf` does
not exist yet. PyPI's **pending publisher** flow solves this: register the
publisher (project name `ocpf`, owner `bwbensonjr`, repo `ocpf-cli`, workflow
`release.yml`, environment `pypi`) *before* the project exists; the first
successful tagged run creates the project and converts it to a normal publisher.

- This is a documented manual step the maintainer performs once, before the first
  `v*` tag is pushed. It is captured in tasks and README so the first release
  does not fail with "project not found / not authorized".

## Risks / Trade-offs

- **[First release fails because the pending publisher was not registered]** →
  Task ordering makes the PyPI registration a hard prerequisite before pushing
  the first tag; README documents it.
- **[`hatch-vcs` produces an unexpected version from a bad/missing tag]** → Tag
  convention is `vX.Y.Z`; a test build (`uv build` on a throwaway tag or via
  TestPyPI) is included as a verification step before the real release.
- **[Publishing a broken artifact]** → `pytest` gates the release job, and
  `uv build` output is checked (metadata/`twine check`-style validation) before
  upload; optionally a TestPyPI dry run first.
- **[Name confusion: repo `ocpf-cli` vs dist `ocpf`]** → README and pyproject
  `urls` make the mapping explicit; classifiers/keywords aid discovery.

## Migration Plan

Additive for users (new install paths) and non-breaking for the command. The only
"breaking" aspect is the distribution name, which has no existing consumers (never
published). Rollback: revert the pyproject/workflow/LICENSE changes; nothing is
yet on PyPI until the first tag is pushed. Order of operations for the first
release: land these changes → register the PyPI pending publisher → push `v0.1.0`
→ verify the published package installs and runs (`uvx ocpf --help`).

## Open Questions

- TestPyPI dry-run before the first real publish — include as a step, or go
  straight to PyPI once the build validates? (Leaning: one TestPyPI dry run for
  the very first release, then PyPI-only thereafter.)
