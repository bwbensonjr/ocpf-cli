# OCPF Command Line Interface

`ocpf` is an opinionated command-line interface to the Massachusetts
[Office of Campaign and Political Finance](https://www.ocpf.us/) (OCPF) API
(`https://api.ocpf.us/`). It turns a recurring, multi-step lookup — "who is
running in this district and how much have they raised and spent?" — into a
single command.

## Install

Run it with no install at all using [`uvx`](https://docs.astral.sh/uv/):

```bash
uvx ocpf race 37th
```

Or install the `ocpf` command onto your PATH:

```bash
pipx install ocpf     # isolated, recommended
pip install ocpf      # into the current environment
```

Then:

```bash
ocpf --help
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
$ ocpf race "1st Suffolk"
error: "1st Suffolk" matches more than one legislative district
  130  Senate, 1st Suffolk
  323  House, 1st Suffolk
$ ocpf race 130 
District:  Senate, 1st Suffolk (code 130)
Election:  primary 9/1/2026, general 11/3/2026
As of:     6/30/2026 (year-to-date, cumulative)

Candidate             Party  Inc   Raised YTD    Spent YTD  Cash on Hand
--------------------  -----  ---  -----------  -----------  ------------
Collins, Nicholas P.  -      *    $246,711.71  $164,522.67   $100,567.72
Gayle, Latoya         -            $49,560.05   $40,197.42    $18,760.46
Shaw, Malik           -               $778.50      $505.37       $273.13
D'Angelo, Marcus      -               $405.00      $157.04       $247.96
Skeens, Juwan         -                $48.02       $90.00        $35.30
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
$ ocpf filer "Collins" --year 2026
Filer:      Collins, Nicholas P.  (cpfId 15084)
Committee:  Collins Committee
Party:      Democratic    Type: Legislative Candidates
Office:     Senate, 1st Suffolk
Status:     active
Organized:  3/9/2010
Treasurer:  Donna Blythe-McColgan

Year-to-date (as of 6/30/2026):
  Raised YTD:    $246,711.71
  Spent YTD:     $164,522.67
  Cash on Hand:  $100,567.72

Recent reports:
Type            Period   Filed            Receipts  Expenditures
--------------  -------  --------------  ---------  ------------
Deposit Report  7/16/26  Fri, 7/17/2026  $3,850.00         $0.00
Deposit Report  7/15/26  Fri, 7/17/2026  $4,475.00         $0.00
Deposit Report  7/15/26  Fri, 7/17/2026  $6,110.00       $241.41
Deposit Report  7/8/26   Fri, 7/17/2026    $150.00         $5.93
Deposit Report  7/3/26   Fri, 7/17/2026    $850.00        $33.58
```

## Scope

v1 covers **legislative** races (House and Senate). Other office types
(statewide, county, mayoral, ballot question), drill-down into individual
reports/donors/expenditures, and free-text candidate-name search are out of
scope. See `openspec/` for the design and specifications.

## Development

The project is managed with [`uv`](https://docs.astral.sh/uv/). From a clone of
this repository:

```bash
uv sync --extra dev     # runtime deps + pytest/respx
uv run pytest           # run the test suite
uv run ocpf race 37th   # run the CLI from source
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
