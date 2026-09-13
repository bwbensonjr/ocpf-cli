## MODIFIED Requirements

### Requirement: District resolution

The system SHALL resolve the `<district>` argument to the single OCPF district
the name identified **in the requested year**. It SHALL accept either a raw
numeric district code or a name matched case-insensitively against district
descriptions, and it SHALL restrict matches to legislative offices (House and
Senate).

Name matching SHALL be tolerant of notation that varies between sources: `&` and
`and` are equivalent, and ordinal words (`First`, `Second`, `Third`) are
equivalent to their numeric forms (`1st`, `2nd`, `3rd`). Word order remains
significant.

A district that existed in the requested year SHALL be resolvable by name even
if it has since been retired at redistricting and no longer appears in the
current district reference. This SHALL hold for years in which no source of
district *codes* covers the requested year: where the districts that held a
special election that year are known by name from the candidates' filings, those
names SHALL be resolvable.

A resolved district SHALL carry its district code whenever the code can be
established from a source that ties it to the requested year. Where a name is
known for the year but no such source reports a code, the district SHALL still
resolve, with its code absent. The system SHALL NOT substitute a code drawn from
a different year, and SHALL NOT report a district as non-existent on the grounds
that only its code is unknown.

When a name cannot be placed in the requested year at all, the system SHALL say
so in terms of that year rather than asserting the name is not a legislative
district.

#### Scenario: Numeric code passed directly

- **WHEN** the user passes a value that is a valid legislative district code
- **THEN** the system uses that code without name matching

#### Scenario: Unique name match

- **WHEN** the district name matches exactly one legislative district description
- **THEN** the system resolves to that district's code and proceeds

#### Scenario: Ambiguous name match

- **WHEN** the district name matches more than one legislative district (e.g.
  `Middlesex` matches several)
- **THEN** the system prints the matching districts with their codes and offices
  and exits without guessing

#### Scenario: Near-collision names are distinguished

- **WHEN** the user requests `"Suffolk and Middlesex"`
- **THEN** the system resolves to district 166 and does not confuse it with
  `"Middlesex & Suffolk"` (district 151)

#### Scenario: Retired district named for a year it existed

- **WHEN** the user requests a district that existed in the requested year but
  has since been retired at redistricting, such as `"Worcester and Norfolk"` for
  2020
- **THEN** the system resolves it to the code it held in that year and proceeds

#### Scenario: Retired district named for a year with no district-code source

- **WHEN** the user requests a district by the name it held in a year for which
  no district-code source has data, but in which it held a special election,
  such as `"2nd Hampden and Hampshire"` for 2013
- **THEN** the system resolves it rather than reporting that it was not a
  legislative district that year

#### Scenario: Code recovered from the candidates who sought the seat

- **WHEN** a district is resolved by name for such a year and at least one
  candidate who filed for that seat still reports it as the office they sought
- **THEN** the resolved district carries the code those candidates report

#### Scenario: Code unavailable for a district known by name

- **WHEN** a district is resolved by name for such a year but no candidate who
  filed for that seat still reports it as the office they sought
- **THEN** the district resolves with its code absent, and the system does not
  substitute a code the data does not tie to that year

#### Scenario: Retired district named for a year after its retirement

- **WHEN** the user requests a retired district for a year in which it did not
  exist
- **THEN** the system reports that the district did not exist in that year,
  indicating the years in which the name is known, and exits non-zero

#### Scenario: Ordinal words are folded to digits

- **WHEN** the user requests `"First Plymouth & Norfolk"`
- **THEN** the system resolves it to the same district as `"1st Plymouth and
  Norfolk"`

#### Scenario: Current-map resolution is unchanged

- **WHEN** a district name resolves against the current district reference for a
  year in which the current map applies
- **THEN** the system resolves it to the same code it resolved to before
  year-awareness was introduced, without consulting any historical source

#### Scenario: No match

- **WHEN** the district name matches no legislative district in the requested
  year and is not known in any other year
- **THEN** the system prints an error indicating no match and exits non-zero

### Requirement: District filtering

The system SHALL include a candidate in the output when the candidate's
`districtCodeSought` or `districtCodeHeld` equals the resolved district code.

Where the resolved district has no code, no candidate SHALL be matched by code.
A district known only by name carries no code to compare against, and treating
an absent code as matching a row whose own code is missing or zero would include
unrelated candidates.

#### Scenario: Candidate seeking the district

- **WHEN** a candidate's `districtCodeSought` equals the resolved code
- **THEN** the candidate is included

#### Scenario: Incumbent holding the district

- **WHEN** an incumbent's `districtCodeHeld` equals the resolved code
- **THEN** the candidate is included and marked as the incumbent

#### Scenario: Resolved district has no code

- **WHEN** the resolved district carries no code and candidate rows are filtered
  by code
- **THEN** no candidate is matched by code, rather than every candidate whose own
  code is absent or zero

#### Scenario: No candidates found

- **WHEN** no candidate matches the resolved district for the year
- **THEN** the system reports that no candidates were found and exits non-zero

### Requirement: Special election summary table

The system SHALL render a special election's candidates as a table showing, at
minimum, candidate name and the receipts and expenditures their operative filing
reports, with monetary values as formatted currency. The table SHALL be labeled
so that the figures are not mistaken for year-to-date amounts.

Where the district carries no code, the rendered header SHALL name the district
without asserting a code, and the JSON district code SHALL be null rather than a
placeholder value.

#### Scenario: Table columns

- **WHEN** a special-election summary renders in default output
- **THEN** each candidate row shows their name and the receipts and expenditures
  from their operative special-election filing, as formatted currency

#### Scenario: Money columns are labeled as period figures

- **WHEN** a special-election summary renders in default output
- **THEN** the money columns are labeled as the filing period's figures rather
  than as year-to-date figures

#### Scenario: JSON output of a special election summary

- **WHEN** the user passes `--json` with `--special`
- **THEN** the system emits the roster as JSON including each candidate's cpfId,
  the underlying numeric monetary values, the reporting period covered, and the
  identifier of the operative report each figure came from

#### Scenario: District without a code renders and serializes

- **WHEN** a special-election summary renders for a district resolved without a
  code
- **THEN** the header names the district and omits the code, and `--json` carries
  a null district code
