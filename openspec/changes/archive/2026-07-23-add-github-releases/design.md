## Context

`release.yml` runs on `v*` tags with three jobs: `test` → `build` → `publish`
(PyPI via Trusted Publishing). Git tags exist but no GitHub Releases do, so the
Releases page is empty. `CHANGELOG.md` (Keep a Changelog format) already has a
`## [X.Y.Z] - <date>` section per version with the notes we'd want, plus
compare-link references at the bottom.

## Goals / Non-Goals

**Goals:**
- Every published `v*` tag gets a GitHub Release whose notes come from the
  matching `CHANGELOG.md` section.
- The release step never breaks the pipeline (publish has already happened).
- Keep PyPI canonical; no duplicate distribution artifacts on GitHub.

**Non-Goals:**
- No auto-generated changelog from commits/PRs (notes come from CHANGELOG).
- No attaching wheels/sdists to the Release.
- No Zenodo/DOI wiring (possible later; a Release is the prerequisite).

## Decisions

### A separate `github-release` job, gated on publish

Add a job `github-release` with `needs: publish` and `permissions: contents:
write`. Running after `publish` means a Release only appears once the version is
actually on PyPI; scoping `contents: write` to this one job keeps the rest of the
workflow least-privileged (the `publish` job keeps only `id-token: write`).

- **Alternative — fold into the publish job:** would widen that job's
  permissions and couple OIDC publishing with release creation. Rejected.

### Create the release with `gh`, not a third-party action

Use the `gh` CLI (preinstalled on runners) with `GH_TOKEN: ${{ github.token }}`:

```
gh release create "$GITHUB_REF_NAME" --title "$GITHUB_REF_NAME" --notes-file NOTES.md
```

- **Why:** no extra external action to pin/maintain; matches the "fewer moving
  parts" preference. `softprops/action-gh-release` is the main alternative and is
  fine, but adds a dependency for no capability we need.

### Notes sourced from CHANGELOG, with a safe fallback

A small step derives the version from the tag (`${GITHUB_REF_NAME#v}`) and
extracts that version's section from `CHANGELOG.md` — the lines from
`## [X.Y.Z]` up to (not including) the next `## ` heading, trimming the
reference-link lines. If the extracted section is empty (no matching entry), fall
back to `gh release create --generate-notes` so a missing changelog entry
degrades gracefully instead of failing the run.

- Extraction is a short `awk`/`sed` snippet in the workflow; no new script file.

### Pre-release detection

If the tag has a pre-release suffix (e.g. `v1.2.3-rc1`, matched by a `-` after
the version), pass `--prerelease`; otherwise create a normal release (`gh` marks
the newest normal release as "latest" automatically). Current tags are plain
`vX.Y.Z`, so they become latest releases.

### Backfill

`v0.1.0` and `v0.2.0` already exist as tags with CHANGELOG sections but no
Releases. Backfill them once with the same `gh release create` invocation
(pointing at each existing tag), so the Releases history is complete. This is a
maintainer step run from an authenticated `gh`, not part of the workflow.

## Risks / Trade-offs

- **[CHANGELOG heading format drifts and extraction returns empty]** → The
  `--generate-notes` fallback keeps the release from failing; notes may be
  thinner until the heading is fixed.
- **[Release job fails after a successful publish]** → PyPI is already updated, so
  a failed Release is non-fatal to distribution and can be re-run (the job is
  idempotent-ish: re-running on an existing release errors, so re-runs should
  `gh release edit` or be triggered only when missing — acceptable for a rare
  case; documented).
- **[Notes duplicate CHANGELOG]** → Intentional surfacing, not drift: notes are
  generated *from* CHANGELOG at release time, never hand-edited.

## Open Questions

None.
