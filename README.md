# OCPF Command Line Interface

`ocpf` is an opinionated command-line interface to the Massachusetts
[Office of Campaign and Political Finance](https://www.ocpf.us/) (OCPF) API
(`https://api.ocpf.us/`). It turns a recurring, multi-step lookup — "who is
running in this district and how much have they raised and spent?" — into a
single command.

## Install

The project is managed with [`uv`](https://docs.astral.sh/uv/).

```bash
# From a clone of this repository:
uv sync                 # install runtime dependencies
uv sync --extra dev     # ...plus pytest/respx for the test suite
```

Run the CLI without installing it globally:

```bash
uv run ocpf --help
```

## Usage

```bash
ocpf race <district> [--year <year>] [--json]
```

`ocpf race` produces a year-to-date (YTD) financial summary of the legislative
(House or Senate) candidates in a district.

- `<district>` may be a **name** matched case-insensitively against OCPF's
  district descriptions (`&` and `and` are treated alike) or a **raw numeric
  district code**. Ambiguous names are never guessed — the tool prints the
  matching districts with their codes and exits so you can pick one.
- `--year` defaults to the current calendar year.
- `--json` emits the merged, filtered candidate records (including the
  underlying `*Numeric` values) as JSON to stdout. Human status/progress goes
  to stderr, so JSON output stays pipeable.

### Example

```bash
$ uv run ocpf race "Suffolk and Middlesex" --year 2026
District:  Senate, Suffolk and Middlesex (code 166)
Election:  primary 9/1/2026, general 11/3/2026
As of:     6/30/2026 (year-to-date, cumulative)

Candidate                 Party  Inc   Raised YTD    Spent YTD  Cash on Hand
------------------------  -----  ---  -----------  -----------  ------------
Brownsberger, William N.  -      *    $265,435.76  $135,490.74   $326,673.49
Lander, Daniel            -           $117,740.53   $32,674.59   $136,386.28
Wood, Brandon             -                $80.00        $3.00        $77.00

* incumbent (holds this seat)
```

Election dates and the as-of date are **timeline context**. The money is the
single cumulative YTD figure the API provides for each candidate; it is never
split into per-primary and per-general amounts.

### `ocpf filer` — one candidate's filing summary

```bash
ocpf filer <filer> [--year <year>] [--json]
```

`ocpf filer` drills into a single filer: their committee profile, cumulative
YTD finances, and most recent reports.

- `<filer>` may be a **raw numeric cpfId** (works for any filer type) or a
  **candidate name** matched case-insensitively against the legislative field
  for the year. cpfIds are shown by `ocpf race`. As with district names,
  ambiguous names are never guessed — the tool prints the matching filers with
  their cpfIds and exits. Name lookup covers legislative filers; for other
  filer types, pass a cpfId directly.
- `--year` defaults to the current calendar year (used for name resolution and
  YTD context).
- `--json` emits the `filer`, `ytdReport`, and `logReports` records (including
  numeric values) to stdout.

```bash
$ uv run ocpf filer "Brownsberger" --year 2026
Filer:      Brownsberger, William N.  (cpfId 14454)
Committee:  Brownsberger Committee
Party:      Democratic    Type: Legislative Candidates
Office:     Senate, Suffolk and Middlesex
Status:     active
Organized:  12/13/2005
Treasurer:  David Merfeld

Year-to-date (as of 6/30/2026):
  Raised YTD:    $265,435.76
  Spent YTD:     $135,490.74
  Cash on Hand:  $326,673.49

Recent reports:
Type            Period   Filed            Receipts  Expenditures
--------------  -------  --------------  ---------  ------------
Deposit Report  7/20/26  Mon, 7/20/2026    $500.00         $0.00
...
```

## Scope

v1 covers **legislative** races (House and Senate). Other office types
(statewide, county, mayoral, ballot question), drill-down into individual
reports/donors/expenditures, and free-text candidate-name search are out of
scope. See `openspec/` for the design and specifications.

## Development

```bash
uv run pytest       # run the test suite
uv run ocpf ...      # run the CLI from source
```

## Design Guidelines

- Use OpenSpec to draft designs and create change proposals.
- Use [clig.dev](https://clig.dev/) for command line interface guidelines.
- Use the `github.com/bwbensonjr/ocpf-analysis` repository (available
  locally) for information about the OCPF APIs, especially the `/api`
  directory which contains `ENDPOINT-STATUS.md` and other script and
  OCPF API test code.
- Use the `github.com/bwbensonjr/ma-election-db` repository (available
  locally) for information on candidates and districts we might want
  to look up.
