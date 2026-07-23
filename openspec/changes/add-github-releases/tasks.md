## 1. Release-notes extraction

- [x] 1.1 Add a step (in the new job) that derives the version from the tag
  (`${GITHUB_REF_NAME#v}`) and extracts that version's section from
  `CHANGELOG.md` — from `## [X.Y.Z]` up to the next `## ` heading, excluding the
  trailing reference-link lines — into a notes file.
- [x] 1.2 If the extracted notes are empty, arrange to fall back to
  `--generate-notes`.

## 2. `github-release` job

- [x] 2.1 Add a `github-release` job to `.github/workflows/release.yml` with
  `needs: publish` and `permissions: contents: write`.
- [x] 2.2 Check out the repo (at the tag) so `CHANGELOG.md` and `gh` are
  available; set `GH_TOKEN: ${{ github.token }}`.
- [x] 2.3 Create the release with `gh release create "$GITHUB_REF_NAME"
  --title "$GITHUB_REF_NAME"` using the notes file (or `--generate-notes`
  fallback); do not attach any distribution artifacts.
- [x] 2.4 Mark the release as a pre-release when the tag has a pre-release suffix;
  otherwise create a normal release.

## 3. Backfill existing tags

- [ ] 3.1 Create GitHub Releases for the existing `v0.1.0` and `v0.2.0` tags,
  using each version's `CHANGELOG.md` section as the notes.

## 4. Verification

- [x] 4.1 Confirm the workflow YAML is valid and the new job wiring is correct
  (lint / dry review).
- [ ] 4.2 After the next release (or a re-run), confirm the GitHub Release exists
  with CHANGELOG-derived notes and no attached artifacts.
