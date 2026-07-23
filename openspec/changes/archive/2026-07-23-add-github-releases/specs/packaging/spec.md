## ADDED Requirements

### Requirement: GitHub Release per version tag

After a version is successfully published to PyPI, the release automation SHALL
create a corresponding GitHub Release for the same `v*` tag. The release notes
SHALL be sourced from the matching version section of `CHANGELOG.md`, falling
back to auto-generated notes when no matching section exists. The GitHub Release
SHALL NOT attach the distribution artifacts (PyPI remains the canonical
distribution). A tag with a pre-release suffix SHALL be marked as a GitHub
pre-release; a plain `vX.Y.Z` tag SHALL be a normal release.

#### Scenario: Release created after publish

- **WHEN** a `v*` tag is pushed and the PyPI publish succeeds
- **THEN** a GitHub Release for that tag is created with notes taken from the
  matching `CHANGELOG.md` section

#### Scenario: Missing changelog section falls back

- **WHEN** the tag has no matching `CHANGELOG.md` section
- **THEN** the GitHub Release is still created using auto-generated notes rather
  than failing

#### Scenario: Distribution artifacts are not attached

- **WHEN** the GitHub Release is created
- **THEN** it contains release notes but no wheel or sdist attachments, so PyPI
  remains the canonical download

#### Scenario: Pre-release tags are marked

- **WHEN** the pushed tag carries a pre-release suffix (e.g. `v1.2.3-rc1`)
- **THEN** the GitHub Release is marked as a pre-release; a plain `vX.Y.Z` tag is
  a normal (latest) release
