## Why

Pushing a `v*` tag publishes to PyPI but creates no GitHub Release, so the repo's
Releases page is empty and there is no in-repo, per-version record of what
changed, nothing to Watch/subscribe to, and no anchor for release provenance or
citation (e.g. Zenodo DOIs). We already maintain `CHANGELOG.md`, so the notes
exist — they just aren't surfaced as Releases.

## What Changes

- Add a `github-release` job to the release workflow that, after a successful
  PyPI publish on a `v*` tag, creates a corresponding GitHub Release for that
  tag.
- The release body is the matching version's section extracted from
  `CHANGELOG.md`; if no matching section is found, fall back to GitHub
  auto-generated notes so the release never fails on a missing entry.
- PyPI stays the canonical distribution: the GitHub Release carries notes only
  and does **not** attach the wheel/sdist.
- Mark pre-release tags (a tag with a pre-release suffix such as `-rc1`) as a
  GitHub pre-release; plain `vX.Y.Z` tags are normal (latest) releases.
- Backfill GitHub Releases for the existing `v0.1.0` and `v0.2.0` tags from
  their `CHANGELOG.md` sections.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `packaging`: the automated release now also creates a GitHub Release per
  version tag (notes sourced from `CHANGELOG.md`), in addition to the PyPI
  publish.

## Impact

- Files: `.github/workflows/release.yml` (new `github-release` job).
- Permissions: the new job needs `contents: write` (scoped to that job); it uses
  the built-in `GITHUB_TOKEN` and `gh` CLI — no new external action required.
- One-time (maintainer): backfill Releases for `v0.1.0` and `v0.2.0`.
- No change to the package, the PyPI publish, or CLI behavior.
