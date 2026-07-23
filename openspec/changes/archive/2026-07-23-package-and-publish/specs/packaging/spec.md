## ADDED Requirements

### Requirement: PyPI distribution under the `ocpf` name

The project SHALL be published to PyPI as the distribution named `ocpf`, exposing
the `ocpf` console command. Installing the distribution SHALL make the `ocpf`
command available.

#### Scenario: Zero-install run with uvx

- **WHEN** a user runs `uvx ocpf race 37th`
- **THEN** the `ocpf` command runs without a prior explicit install and without
  needing a `--from` override

#### Scenario: Install with pipx or pip

- **WHEN** a user runs `pipx install ocpf` (or `pip install ocpf`)
- **THEN** the `ocpf` command is installed and available on the PATH

#### Scenario: Command name unchanged

- **WHEN** the distribution is installed under the name `ocpf`
- **THEN** the invoked command is `ocpf` (the console script and public CLI
  behavior are unchanged from the source checkout)

### Requirement: Complete distribution metadata

The package metadata SHALL be complete enough to present a correct PyPI project
page and to support resolver filtering. It SHALL include the author, an MIT
license with a corresponding `LICENSE` file, project URLs (home page, repository,
and issue tracker), keywords, and trove classifiers covering the supported Python
versions (3.11, 3.12, 3.13), a console environment, and the MIT license.

#### Scenario: Built artifact carries required metadata

- **WHEN** the distribution is built
- **THEN** the resulting metadata declares the MIT license, the author, the
  project URLs, and classifiers for Python 3.11–3.13, and a `LICENSE` file is
  included in the distribution

#### Scenario: Metadata validation passes

- **WHEN** the built sdist and wheel are validated for packaging metadata
- **THEN** validation reports no errors that would block a PyPI upload

### Requirement: Tag-driven versioning

The package version SHALL be derived from the git release tag rather than being
hardcoded, so that the published version always matches the tag that triggered the
release.

#### Scenario: Version matches the release tag

- **WHEN** a release is built from the git tag `vX.Y.Z`
- **THEN** the built distribution's version is `X.Y.Z`

#### Scenario: No hardcoded version to drift

- **WHEN** the project source is inspected
- **THEN** the version is declared dynamic (sourced from version control), not a
  static literal that must be manually kept in sync with the tag

### Requirement: Continuous integration test gate

The repository SHALL run the automated test suite in CI on pushes and pull
requests across the supported Python versions.

#### Scenario: Tests run across supported Python versions

- **WHEN** a change is pushed or a pull request is opened
- **THEN** CI runs the test suite on Python 3.11, 3.12, and 3.13

### Requirement: Automated, test-gated release via Trusted Publishing

Publishing to PyPI SHALL be automated and triggered by pushing a version tag
matching `v*`. The release SHALL run the test suite before building, build the
sdist and wheel, and publish using PyPI Trusted Publishing (OIDC) without any
long-lived API token stored in the repository.

#### Scenario: Tag triggers a release

- **WHEN** a maintainer pushes a tag matching `v*`
- **THEN** the release workflow runs the tests, builds the distribution, and
  publishes it to PyPI

#### Scenario: Failing tests block the publish

- **WHEN** the test suite fails during a tagged release run
- **THEN** the distribution is not built or published

#### Scenario: No stored publishing credential

- **WHEN** the release workflow publishes to PyPI
- **THEN** it authenticates via OIDC Trusted Publishing and does not rely on a
  stored PyPI API token secret

#### Scenario: First release bootstraps via pending publisher

- **WHEN** the project does not yet exist on PyPI and a pending Trusted Publisher
  has been registered for it
- **THEN** the first successful tagged release creates the PyPI project and
  publishes the distribution
