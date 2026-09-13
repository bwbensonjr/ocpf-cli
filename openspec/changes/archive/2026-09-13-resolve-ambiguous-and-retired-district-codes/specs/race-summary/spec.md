## MODIFIED Requirements

### Requirement: District resolution

The system SHALL resolve the `<district>` argument to the single OCPF district
the name identified **in the requested year**. It SHALL accept either a raw
numeric district code or a name matched case-insensitively against district
descriptions, and it SHALL restrict matches to legislative offices (House and
Senate).

A numeric district code SHALL be validated against the map for the **requested
year**, not only against the present map. A code that a year-scoped source
reports for that year SHALL be accepted for it. In particular, any district code
the system itself reports for a year SHALL be accepted as input for that year.

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

It SHALL also hold where the converse is true — the district *code* is
established for the requested year but no candidate who sought that seat still
reports it as the office they seek. Resolution SHALL NOT depend on whether a
seat's former candidates ran for it again. Where the candidates' current offices
cannot name such a code, the system SHALL establish the name from the office
recorded on the filings those candidates made in the requested year, which names
the seat as it stood when it was filed for.

A resolved district SHALL carry its district code whenever the code can be
established from a source that ties it to the requested year. Where a name is
known for the year but no such source reports a code, the district SHALL still
resolve, with its code absent. The system SHALL NOT substitute a code drawn from
a different year, and SHALL NOT report a district as non-existent on the grounds
that only its code is unknown.

Where a name matches more than one district in the present map, the system SHALL
NOT report that as ambiguous without first consulting the map for the requested
year. Where the year's map yields exactly one match, that district SHALL be
resolved. Ambiguity SHALL be reported only when the requested year's own map
cannot narrow the field, and the candidates offered SHALL be districts that
existed in that year.

Within any one map, an exact name match SHALL take precedence over a match that
is merely a prefix or substring. This precedence SHALL NOT collapse a genuine
ambiguity: where a name matches more than one district *exactly* — as a numbered
district name shared by a House and a Senate seat does — the result remains
ambiguous.

When a name cannot be placed in the requested year at all, the system SHALL say
so in terms of that year rather than asserting the name is not a legislative
district.

#### Scenario: Numeric code passed directly

- **WHEN** the user passes a value that is a valid legislative district code
- **THEN** the system uses that code without name matching

#### Scenario: A code the system prints is a code it accepts

- **WHEN** the system reports a district code for a year, such as code 140 for
  `"Worcester and Norfolk"` in 2020
- **THEN** passing that code for that same year resolves to the same district

#### Scenario: Retired code accepted for a year a year-scoped source reports it

- **WHEN** the user passes a district code that the present map omits but a
  year-scoped source reports for the requested year, such as code 127 for 2020
- **THEN** the system resolves it rather than reporting it is not a legislative
  district code in that year

#### Scenario: Unique name match

- **WHEN** the district name matches exactly one legislative district description
- **THEN** the system resolves to that district's code and proceeds

#### Scenario: Ambiguous name match

- **WHEN** the district name matches more than one legislative district in the
  requested year (e.g. `Middlesex` matches several)
- **THEN** the system prints the matching districts with their codes and offices
  and exits without guessing

#### Scenario: Retired name that prefixes two current district names

- **WHEN** the user requests a district whose name matches two districts in the
  present map only as a prefix, but exactly one district in the requested year's
  map — such as `"Plymouth and Norfolk"` for 2016 or 2020, which the present map
  splits into `1st Plymouth and Norfolk` and `2nd Plymouth and Norfolk`
- **THEN** the system resolves it to the single district of that name in the
  requested year rather than reporting it as ambiguous

#### Scenario: Ambiguity candidates are districts of the requested year

- **WHEN** a name is genuinely ambiguous for the requested year
- **THEN** the districts offered are ones that existed in that year, and the
  system does not suggest districts that did not

#### Scenario: An exact match does not collapse a genuine ambiguity

- **WHEN** a name matches more than one district exactly, such as `"1st Suffolk"`
  naming both a House and a Senate seat
- **THEN** the result remains ambiguous and the system exits without guessing

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

#### Scenario: Seat named from the filings when every candidate has moved on

- **WHEN** the user requests a district by the name it held in a year for which a
  district-code source has data, but every candidate who sought that seat has
  since sought a different one — such as `"1st Plymouth and Bristol"` for 2014,
  whose candidates now report districts 170 and 157
- **THEN** the system resolves it to the code it held that year rather than
  reporting that it was not a legislative district that year

#### Scenario: Candidates who stayed put still name the seat

- **WHEN** at least one candidate who sought the seat still reports it as the
  office they seek
- **THEN** the system names the district from those candidates and makes no
  further request, resolving to the same district it resolved to before the
  filings were consulted

#### Scenario: A code that cannot be named is not reported as non-existent

- **WHEN** a district code carries candidates for the requested year but neither
  the candidates' current offices nor their filings for that year name it
- **THEN** the system does not assert that the district did not exist that year
  on the grounds that only its name is unknown

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
