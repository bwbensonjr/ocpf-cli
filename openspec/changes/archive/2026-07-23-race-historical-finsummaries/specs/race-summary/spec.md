## ADDED Requirements

### Requirement: Historical financial data fallback

When the current-cycle legislative feeds yield no candidate with money for the
resolved district and year, the system SHALL fall back to the district-scoped
`onballot/finsummaries/{year}/{districtCode}` endpoint and use its rows as the
candidate field. Selection SHALL be driven by data availability, not a hardcoded
year cutoff.

The system SHALL normalize each `finsummaries` row into the shared candidate-row
shape used by the current-cycle path: the currency strings `receipts`,
`expenditures`, and `endBalance` SHALL be parsed into the numeric fields
`receiptsYtdNumeric`, `expendituresYtdNumeric`, and `currentCashOnHandNumeric`
respectively, and the `isIncumbent` and `isWinner` flags SHALL be carried
through. Because `finsummaries` is district-scoped by URL and returns
`districtCode: 0` on every row, historical rows SHALL NOT be run through the
`districtCodeSought`/`districtCodeHeld` filter.

#### Scenario: Current feeds empty, historical data available

- **WHEN** the current-cycle feeds return no candidate with money for the
  resolved district (e.g. `ocpf race --year 2008 37th`)
- **THEN** the system fetches `onballot/finsummaries/{year}/{districtCode}` and
  renders the candidates from that feed

#### Scenario: Current feeds have data

- **WHEN** the current-cycle feeds return at least one candidate with money for
  the resolved district
- **THEN** the system uses the current-cycle field and does not call the
  `finsummaries` endpoint

#### Scenario: Currency strings normalized to numbers

- **WHEN** a `finsummaries` row reports `receipts` as `"$63,727.50"`
- **THEN** the normalized record carries `receiptsYtdNumeric` of `63727.50`, and
  likewise for expenditures and `endBalance` mapped to
  `currentCashOnHandNumeric`

#### Scenario: Incumbency from the flag

- **WHEN** a historical row has `isIncumbent` true
- **THEN** the candidate is marked as the incumbent, independent of
  `districtCode` (which is `0` in this feed)

#### Scenario: No candidates in either source

- **WHEN** neither the current-cycle feeds nor `finsummaries` return candidates
  for the resolved district and year
- **THEN** the system reports that no candidates were found and exits non-zero

## MODIFIED Requirements

### Requirement: YTD summary table

The system SHALL render the matched candidates as a table. For current-cycle
data the table SHALL include, at minimum: candidate name, party, an incumbent
marker, year-to-date receipts, year-to-date expenditures, and current cash on
hand. For historical (final-totals) data the table SHALL instead show
final-total column labels (`Raised` / `Spent` / `End Bal`) and add a winner
marker column driven by `isWinner`. Monetary values SHALL be shown as formatted
currency in the default (human) output.

#### Scenario: Table columns

- **WHEN** the summary renders current-cycle data in default output
- **THEN** each candidate row shows name, party, incumbent marker, receipts YTD,
  expenditures YTD, and cash on hand

#### Scenario: Historical table columns

- **WHEN** the summary renders historical (final-totals) data in default output
- **THEN** each candidate row shows name, party, incumbent marker, a winner
  marker, and final-total receipts, expenditures, and end balance, with the
  money columns labeled as final totals rather than YTD

#### Scenario: JSON output of the summary

- **WHEN** the user passes `--json`
- **THEN** the system emits the matched candidate records as JSON, including the
  underlying numeric monetary values; for historical data the records also
  include the `isWinner` flag

### Requirement: Election timeline context, not money segmentation

The system SHALL present primary and general elections as timeline context and
SHALL NOT split candidates' money by election. It SHALL show the primary and
general election dates for the year (from the API filing schedule) and, when the
underlying figures carry a reporting date, the as-of reporting date. It SHALL
present the money as the single cumulative figure the source provides.

#### Scenario: Election dates shown as context

- **WHEN** the summary renders in default output
- **THEN** the header shows the primary and general election dates for the year

#### Scenario: As-of date shown for current-cycle data

- **WHEN** the summary renders current-cycle data in default output
- **THEN** the header indicates the as-of reporting date of the year-to-date
  figures (derived from the candidates' latest report end dates)

#### Scenario: No as-of date for historical data

- **WHEN** the summary renders historical (final-totals) data, which carries no
  report end date
- **THEN** the header omits the as-of line, and no lagging-filer note is shown

#### Scenario: Money is not segmented by election

- **WHEN** a district has both a primary and a general election in the year
- **THEN** each candidate's receipts, expenditures, and cash on hand (or end
  balance) are shown as a single cumulative figure, not divided into primary and
  general amounts
