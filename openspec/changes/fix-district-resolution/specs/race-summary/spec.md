## MODIFIED Requirements

### Requirement: District resolution

The system SHALL resolve the `<district>` argument to the single OCPF district
code that district had **in the requested year**. It SHALL accept either a raw
numeric district code or a name matched case-insensitively against district
descriptions, and it SHALL restrict matches to legislative offices (House and
Senate).

Name matching SHALL be tolerant of notation that varies between sources: `&` and
`and` are equivalent, and ordinal words (`First`, `Second`, `Third`) are
equivalent to their numeric forms (`1st`, `2nd`, `3rd`). Word order remains
significant.

A district that existed in the requested year SHALL be resolvable by name even
if it has since been retired at redistricting and no longer appears in the
current district reference. When a name cannot be placed in the requested year,
the system SHALL say so in terms of that year rather than asserting the name is
not a legislative district.

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
