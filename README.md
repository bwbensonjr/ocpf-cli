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
ocpf race <district> [--year <year>] [--special] [--stage primary|general] [--json]
```

`ocpf race` produces a year-to-date (YTD) financial summary of the legislative
(House or Senate) candidates in a district.

- `<district>` may be a **name** matched case-insensitively against OCPF's
  district descriptions (`&` and `and` are treated alike) or a **raw numeric
  district code**. Ambiguous names are never guessed — the tool prints the
  matching districts with their codes and exits so you can pick one.
- `--year` defaults to the current calendar year, and **district names resolve
  against the map as it stood in that year**. A district retired at
  redistricting is still reachable for the years it existed:
  `ocpf race "Worcester and Norfolk" --year 2020` resolves to Senate code 140,
  which no longer appears in OCPF's current district list. Asking for a year in
  which the name was not a district says so and names where it was, rather than
  claiming the name is invalid.
- Ordinal words are matched alike to their digit forms, so
  `"First Plymouth & Norfolk"` and `"1st Plymouth and Norfolk"` reach the same
  district. Word order still matters: `"Middlesex & Suffolk"` and
  `"Suffolk and Middlesex"` are two different seats.
- Resolving a **pre-2020** retired district costs a sweep of the office's code
  range (76 requests for Senate, 164 for House, plus a lookup per populated
  code) because no year-scoped district list exists. Progress goes to stderr;
  expect roughly 20-30 seconds. Current districts and 2020-onward years are
  unaffected and cost nothing extra.
- A district that held a **special election** is resolved from the filings
  instead, and skips that sweep entirely. This covers the pre-2020 odd years
  (2007, 2013, 2015, 2017, 2019) where no district list has data at all — the
  years specials happen. Such a district may render **without a code**:

  ```
  District:  Senate, 1st Hampden & Hampshire
  ```

  That is not a missing value to work around. OCPF numbers a district only in
  sources that stop before these years, and a seat's number is recovered from the
  candidates who sought it — so when every one of them has since run for
  something else, the name is known and the number is not. `--json` reports
  `"districtCode": null` for these, and the district resolves and reports
  normally in every other respect.
- `--special` summarizes a **special election** held that year instead of the
  regular cycle. See below.
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

### Special elections

OCPF's on-ballot and legislative feeds are keyed to the regular election cycle
and carry no special elections, so a year without a regular contest looks empty:

```bash
$ ocpf race "6th Bristol" --year 2013
error: No candidates found for House, 6th Bristol (code 214) in 2013; if a
special election was held that year, reach it with --special
```

`--special` builds the field from the candidates' own special-election filings
instead:

```bash
$ ocpf race "6th Bristol" --year 2013 --special
note: a special primary was also held (7/1/2013 - 7/26/2013); see it with --stage primary
District:  House, 6th Bristol (code 214)
Election:  special general
Period:    7/27/2013 - 8/23/2013

Candidate           Raised in Period  Spent in Period
------------------  ----------------  ---------------
Steinhof, David           $13,530.00        $6,829.57
Fiola, Carole              $6,535.00       $22,751.61
Dennis, David J.           $4,180.00        $4,753.94
Kilby, Bradford L.         $3,235.00        $3,548.00
Potvin, Gerald                 $0.00        $1,974.02

Figures are each candidate's operative filing for the period above, not year-to-date.
OCPF publishes no election date for a special election.
```

Four things to read carefully in that table:

- **The roster is who *filed*, not who appeared on a ballot.** A candidate who
  pulled papers for the special and withdrew still filed reports, so they still
  appear. The primary field is usually larger than the general field, and both
  are true answers to different questions.
- **The money covers that stage's window only**, not the whole campaign. A
  pre-election special report covers the period since the pre-primary one, so
  adding a candidate's primary and general figures is closer to their campaign
  total than either alone. For an exact cumulative window, use
  `ocpf totals <filer> --start ... --end ...`.
- **`--stage primary` or `--stage general` picks the stage.** With neither, the
  general is summarized — it is the election, of which the primary is a
  preliminary round — and a note names the primary if one was held. A district
  that held only one stage needs no flag.
- **There is no election date**, because OCPF publishes none for a special
  (`filingSchedules/2013` returns empty strings for both dates). The header names
  the period the filings cover, which is sourced, rather than a date inferred
  from it, which would not be.

`--json` works here too, and carries each candidate's cpfId, the numeric
receipts and expenditures, the window their own filing covers, and the id of the
operative report each figure came from:

```bash
$ ocpf race "6th Bristol" --year 2013 --special --json | jq '.[0]'
{
  "cpfId": 15658,
  "name": "Steinhof, David",
  "districtCode": 214,
  "office": "House",
  "districtDescription": "6th Bristol",
  "stage": "general",
  "reportingPeriod": {
    "start": "2013-07-27",
    "end": "2013-08-23",
    "label": "7/27/2013 - 8/23/2013"
  },
  "reportingPeriodSpan": { ... },
  "reportId": 199084,
  "receipts": 13530.0,
  "expenditures": 6829.57
}
```

A candidate who filed nothing for the stage is shown as `not reported` rather
than dropped or shown as `$0.00`, and their `receipts` and `reportId` are
`null`. Figures always come from the **operative** filing: Steinhof amended his
2013 pre-election report from `$9,940.00` as filed up to `$13,530.00`, and the
amended figure is the one reported.

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

### `ocpf expenditures` — who a committee paid

```bash
ocpf expenditures <filer> [--year <year>] [--since <date>] [--until <date>]
                          [--vendor <text>] [--min-amount <n>] [--max-amount <n>]
                          [--by-vendor] [--limit <n>] [--json]
```

`ocpf expenditures` lists the payments a single committee has made, drawn from
every expenditure record OCPF holds for that filer.

- `<filer>` resolves exactly as it does for `ocpf filer`: a numeric cpfId, or a
  legislative candidate name.
- Filters combine: `--year`, `--since`/`--until` (`YYYY-MM-DD` or `M/D/YYYY`),
  `--vendor` (case-insensitive substring), `--min-amount`/`--max-amount`.
- `--by-vendor` totals by payee instead of listing records.
- `--limit` caps displayed rows; the reported total always describes the full
  filtered set, not just what fit on screen.

```bash
$ ocpf expenditures Uyterhoeven --year 2026 --by-vendor --limit 6
Vendor                                    Total  Count  Src
-----------------------------------  ----------  -----  ----
EAST COAST PRI                       $66,034.34     11  bank
OUTGOING WIRE TRANSFER               $23,000.00      2  bank
Jovana Calvillo (4 filed spellings)  $20,250.00      4  bank
AMALGAMATED BANK                     $17,000.00      2  bank
MAGDA MOHAMED (2 filed spellings)    $16,250.00      6  bank
EAST COAST PR                         $7,463.34      1  bank

Showing 6 of 78 vendors (--limit 6).
Total: $210,413.30  (181 records, 78 vendors)
```

**A filter that matches nothing is an answer, not an error** — it exits zero, so
you can tell "they paid them nothing" apart from "the lookup failed":

```bash
$ ocpf expenditures Uyterhoeven --vendor "Connection Strategies"
No expenditures matching vendor "Connection Strategies"
(searched 1,019 records, 1/2020-8/2026)
$ echo $?
0
```

Three things to know about the underlying data:

- **`bank` marks bank-reported records.** Their payee comes off a bank statement
  and can be an opaque description (`OUTGOING WIRE TRANSFER`) rather than the
  true recipient. An absence of matches proves no *disclosed* payment; it cannot
  rule out one routed through an undisclosed wire.
- **Payees are shown as OCPF clarified them.** Where OCPF supplied a
  `clarifiedName`, that is the payee used and grouped on, with the filed string
  shown alongside (`Middle Seat (OUTGOING WIRE TRANSFER)`); a rollup row notes
  how many filed spellings it covers. Variants OCPF has *not* clarified are
  never merged.
- **The total will not match `ocpf filer`'s YTD spent figure**, and that is
  correct: item search includes out-of-pocket candidate expenditures that the
  YTD bank figure excludes.

### `ocpf totals` — money in a window, not a calendar year

```bash
ocpf totals <filer> --start <date> --end <date> [--category receipts|expenditures]
                    [--resolve-year <year>] [--json]
```

`ocpf race` and `ocpf filer` report the year-to-date figure OCPF publishes. That
figure is a **full calendar year**, so once a cycle is over it includes money
raised *after* the election — and post-election money follows the outcome, since
winners keep raising and losers stop. For cpfId 14902:

| Year | Through 10/31 | Full calendar year | Raised after 10/31 |
|---|---|---|---|
| 2024 | $401,190.59 | $560,090.46 | 28% |
| 2020 | $32,935.00 | $111,125.63 | 70% |

Any analysis that treats the published number as pre-election money is wrong by
that much, in the direction that flatters the result. `ocpf totals` measures an
explicit window instead:

```console
$ ocpf totals 14902 --start 2024-01-01 --end 2024-10-31
cpfId     14902
Category  receipts
Window    2024-01-01 to 2024-10-31
Records   1,277
Total     $401,190.59

$ ocpf totals 14902 --start 2023-11-01 --end 2024-10-25 --category expenditures
cpfId     14902
Category  expenditures
Window    2023-11-01 to 2024-10-25
Records   845
Total     $397,182.30
```

Notes:

- **Both bounds are required**, and the window is printed with the figure. An
  unbounded total is the ambiguous number this command exists to replace, so it
  cannot be produced by leaving an option off.
- **Windows may cross a year boundary**, which matters for an election held
  early in a calendar year, and coverage reaches back to at least 2010.
- **One request per invocation.** The total is the API's own arithmetic over the
  filtered set, not a sum of records fetched locally — which is why the command
  verifies the date filter was actually applied before reporting anything.
- **An empty window is a finding, not an error**: zero records reports `$0.00`
  and exits zero.
- The total will not match `ocpf filer`'s year-to-date figure even for a
  full-year window, for the same reason `ocpf expenditures` does not: item
  search includes out-of-pocket candidate expenditures that the year-to-date
  bank figure excludes.

### `ocpf reports` / `ocpf report` — the filings themselves

```bash
ocpf reports <filer> [--type <text>] [--year <year>] [--since <date>] [--until <date>]
                     [--limit <n>] [--include-superseded] [--resolve-year <year>] [--json]
ocpf report <report-id> [--schedule <name>]... [--json]
```

`ocpf reports` lists what a committee has actually filed; `ocpf report` shows
one filing in full — the same document the OCPF web UI serves at
`Reports/DisplayReport?id=N`.

This is the only way to see **special-election** money. The year-to-date feeds
behind `ocpf race` and `ocpf filer` carry one cumulative figure per filer per
calendar year and are never segmented by election, so a special held in
February is invisible in them. The filing that covers that window is not:

```console
$ ocpf reports 14819 --type "pre-election"
Report  Type                                Period                  Filed       Receipts  Expenditures  Amd
------  ----------------------------------  ----------------------  ---------  ---------  ------------  -----
566246  Pre-election Report (ND)            8/23/2014 - 10/17/2014  3/9/2016   $1,075.00       $155.00  amend
170378  Pre-election Report (Special) (ND)  2/16/2013 - 3/15/2013   5/8/2013   $3,512.97    $10,036.61  amend
103215  Pre-election Report (ND)            8/30/2008 - 10/17/2008  12/1/2009  $5,580.00     $7,148.83  amend

3 reports

$ ocpf report 170378
Report     170378
Type       Pre-election Report (Special) (ND)
Period     2/16/2013 - 3/15/2013
Filed      5/8/2013
Committee  Matewsky Committee
Candidate  Matewsky, Wayne
Office     House, 28th Middlesex
Treasurer  Gerard Osterofsky
Bank       East Boston Savings
Amendment  amends report 170376

                               Amount
-------------------------  ----------
Start balance               $7,953.94
Receipts (total)            $3,512.97
Expenditures (total)       $10,036.61
End balance                 $1,430.30

https://www.ocpf.us/Reports/DisplayReport?menuHidden=true&id=170378
```

Notes:

- **A former candidate is reachable by cpfId, not by name.** `<filer>` resolves
  a name against the *current* legislative field, so someone who left office —
  or who lost a special and never served — has no name to match, and the error
  says to pass their cpfId. That is the same limitation `ocpf filer` and
  `ocpf expenditures` have, and it bites hardest here, because the filings worth
  reading often belong to exactly those candidates. `ocpf reports 14819` works
  where `ocpf reports Matewsky` does not.
- **The listing covers the filer's whole history**, not just the current year —
  otherwise a 2013 filing would be unreachable unless you already knew to ask
  for 2013. Narrow it with `--type`, `--year` or `--limit`; a twenty-year
  depository committee has several hundred reports, mostly routine monthly
  deposit and bank reports.
- **`--type` matches the type description as a substring**, which is deliberate:
  the same report type has a depository and a non-depository spelling
  (`Pre-Election Report (Special)` and `Pre-election Report (Special) (ND)`) and
  `--type "pre-election"` gets both.
- **Date bounds test the reporting period for overlap**, not containment, so
  `--since 2013-03-01 --until 2013-03-01` finds the filing covering that date.
- **Superseded filings are hidden by default.** An amended filing shows once, as
  the operative version; `--include-superseded` adds the replaced versions, and
  rows are marked `amend` (this filing amends an earlier one) or `amended` (a
  later filing replaces it).
- **`--schedule` prints line items** and is repeatable:
  `receipts`, `expenditures`, `out-of-pocket`, `in-kind`, `liabilities`,
  `subvendor`. Totals are shown without them by default.
- **Per-filing totals are not year-to-date totals.** Each row describes its own
  reporting period, which is what makes a pre-election figure a pre-election
  figure.
- The filed PDF is at `https://api.ocpf.us/report/pdf/<report-id>`.

## Scope

v1 covers **legislative** races (House and Senate). Other office types
(statewide, county, mayoral, ballot question) are reachable by cpfId but not by
name. Contribution and subvendor search, cross-filer vendor search ("every
committee that paid this firm"), and free-text candidate-name search are out of
scope. Reports are reachable per filer (`ocpf reports <filer>`); cross-filer
report search — "every pre-election special filed this cycle" — is not yet
exposed. See `openspec/` for the design and specifications.

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
