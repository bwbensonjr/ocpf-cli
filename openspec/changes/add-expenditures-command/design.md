## Context

See proposal.md — Why. The constraints that shape the approach:

- **The endpoint is documented, but not where the project looks.**
  `../ocpf-analysis/api/ENDPOINT-STATUS.md` lists `search/items` with a one-line
  description and no parameters. OCPF actually publishes a complete OpenAPI spec
  at `https://api.ocpf.us/swagger/v1/swagger.json` enumerating all 29 query
  parameters. Everything below was verified against the live API against
  cpfId 17436 (1,019 expenditure records, $394,691.07, 1/2020–8/2026).
- **`search/items` is loosely typed and fails open.** `SearchTypeCategory`
  selects the record kind: `B` expenditures, `R` receipts, `S` subvendor
  payments, `D` donations (empty in practice). Any *unrecognized* value —
  including `E`, `expenditures`, `EXP`, and the empty string — silently returns
  **receipts**. There is no error. A typo in this one parameter produces a
  plausible-looking table of the wrong direction of money.
- **Filter parameters are also silently ignored when misnamed.** `Name` filters
  the counterparty and works. `VendorName` appears in the swagger spec but is
  inert: passing it returns the entire unfiltered database (1,823,947 records,
  $1.55B). An ignored filter is indistinguishable from a filter that matched
  everything.
- **Response shape**: `{"summary": {count, total, totalDisplay, description},
  "items": [...]}`. `summary` is `null` unless `withSummary=true`. Expenditure
  items carry `vendor`, `purpose`, `clarifiedName`, `clarifiedPurpose`, `date`
  (`M/D/YYYY`), `amount` (`"$1,234.56"` — a *string*), `recordTypeDescription`,
  `reportId`, and `sourceLink`/`sourceDescription`.
- **Existing seam**: `api.get_json(path, params)` already takes a params dict and
  raises `OcpfApiError`. `render` provides `render_table`, `emit_json`,
  `format_currency`, `parse_currency`, `status`, `error`. Filer resolution lives
  in `commands/filer.py` and is currently private to that module.

## Goals / Non-Goals

**Goals:**

- A `search/items` client that makes the fail-open hazards above structurally
  unreachable rather than merely documented.
- Retrieval that is complete or loudly incomplete — never quietly truncated.
- Filer resolution shared with `ocpf filer` by extraction, not duplication or
  cross-command import.

**Non-Goals:**

- A general query builder over all 29 `search/items` parameters. This change
  wires the handful the command needs; the rest stay unexposed until something
  wants them.
- Reconciling the command's total against the filer's YTD `expendituresYtd`
  figure. They legitimately differ (2026: $210,413 from item search vs $204,565
  YTD) because item search includes out-of-pocket candidate expenditures that
  the YTD bank figure does not. Explaining that divergence is a documentation
  matter, not a computation.
- Canonicalizing payee names. See Decision 6.

## Decisions

### 1. Record kind is an enum in code, never a user-supplied string

`SearchTypeCategory` is set from a module-level constant
(`CATEGORY_EXPENDITURES = "B"`), never interpolated from CLI input, and no flag
exposes it. Because an unrecognized value silently returns receipts, the fetch
layer additionally **asserts the returned records are expenditures** — receipt
items have a `fullNameReverse`/`contributorCpfId` shape and lack `vendor`, so
the presence of the wrong shape raises `OcpfApiError` rather than rendering.

*Alternative considered*: trusting the parameter and skipping validation. Fine
until a future `--receipts` flag or a refactor lets a bad value through, at
which point the failure is silent and the output is credible-looking and wrong.
This is exactly the class of bug worth paying two lines to make impossible. The
spec encodes it ("SHALL fail rather than display money the filer received as
money the filer paid") so it survives refactoring.

### 2. Server-side pagination, client-side filtering

Fetch with `CpfId` + `SearchTypeCategory=B` + `withSummary=true`, paginating on
`StartIndex`/`PageSize` until `len(items) >= summary.count`. Then apply
`--year`, `--since`, `--until`, `--vendor`, `--min-amount`, `--max-amount`
**locally**.

Rationale: the API does offer `StartDate`/`EndDate`/`MinAmount`/`MaxAmount`/`Name`,
but pushing filters server-side means every filter's correctness depends on an
API whose sibling parameter (`VendorName`) is provably inert, and a wrongly
ignored filter returns *more* data that still renders as a plausible answer. A
committee's full expenditure history is ~1,000 records — one or two requests —
so local filtering costs nothing and is verifiable in tests without mocking
filter semantics. It also lets `--vendor` do case-insensitive substring matching
with defined behavior instead of whatever `Name` does.

*Trade-off*: a future cross-filer search (no `CpfId`) can return 1.8M records and
**must** push filters server-side. That is out of scope here, and the fetch
function should take the query params as a dict so that path stays open.

### 3. Completeness is checked, not assumed

The fetch loop compares the accumulated record count against `summary.count` and
raises `OcpfApiError` on a shortfall, rather than returning what it got. A
silently short result set understates a total — the specific failure that makes
a campaign-finance tool worse than useless, because the answer looks like an
answer. Guard against a non-advancing page (a page returning zero new items)
to avoid an infinite loop when the API misbehaves.

### 4. Filer resolution moves to a shared module

`resolve_filer`, `FilerMatch`, and `FilerResolutionError` move from
`commands/filer.py` to `src/ocpf_cli/resolve.py`; `commands/filer.py` imports
them. A pure move, no behavior change — `tests/test_filer.py` must pass with only
import paths updated, and that is the check that the move was pure.

*Alternative considered*: `from .filer import resolve_filer` in
`expenditures.py`. Rejected — command modules importing each other's internals
is how a CLI accretes a dependency graph nobody can follow. `districts.py` and
`legislative.py` already establish the shared-module pattern this follows.

### 5. Amounts are parsed once, at the boundary

`amount` arrives as `"$1,234.56"`. The fetch layer converts it to a float via the
existing `render.parse_currency` and attaches it to each record, so filtering,
summing, and grouping all operate on numbers. Formatting back to currency happens
only in the render layer. `--json` emits both the numeric value and the original
string, matching how `race` and `filer` already expose `*Numeric` fields
alongside display values.

### 6. OCPF's clarified payee is honored; no merge is ever inferred

**Revised during implementation.** The original decision was to group strictly on
the filed payee string and never merge variants, on the premise that the only
thing linking `JOVANA CALUILB`, `JIVANA CALVILLE`, `JOVANA CALVILLO` and
`Jovana Calvillo` was our own guess. That premise was wrong: OCPF ships a
`clarifiedName` field carrying **its own** resolution of a payee string, and it
resolves exactly these records.

The command therefore groups on the *effective payee* — `clarifiedName` where
OCPF supplied one, the filed string otherwise — and never infers a merge OCPF
has not made. Two similar-looking unclarified strings stay two rows.

What settled it is a record the original rule would have misreported. Of the
$29,000 in 2026 wire transfers whose payee looked undisclosed, one is disclosed:

| Filed `vendor` | OCPF `clarifiedName` | Amount |
|---|---|---|
| `OUTGOING WIRE TRANSFER` | Middle Seat | $6,000.00 |
| `JOVANA CALUILB` | Jovana Calvillo | $5,250.00 |
| `JIVANA CALVILLE` | Jovana Calvillo | $5,000.00 |

Grouping on the raw string alone would report a known recipient as an anonymous
wire. Suppressing the disclosing authority's own clarification to avoid the
appearance of guessing makes the output less true, not more careful. Only 6 of
181 2026 records carry a clarification, so this is a narrow, high-value case.

*Nothing is hidden by the substitution*: the itemized view renders
`Middle Seat (OUTGOING WIRE TRANSFER)`, each rollup group keeps every filed
spelling it absorbed in `filedAs` and shows the count (`Jovana Calvillo (4 filed
spellings)`), `--json` emits `payee`, `vendor`, `clarifiedName` and
`isClarified` separately, and a stderr legend states that clarified payees are
being shown. A reader can always recover exactly what was filed.

*Alternative considered*: show the clarification in a separate column and still
group on the raw string. Rejected — it keeps the rollup honest but makes the
headline answer ("who did they pay?") wrong by default, which is the question
the command exists to answer.

### 7. Bank-reported records are marked, and their limits stated

`recordTypeDescription` distinguishes `Bank Reported Expenditure` from itemized
committee filings. Bank-reported payees can be opaque (`OUTGOING WIRE TRANSFER`,
$29,000 across three 2026 records for cpfId 17436; `AMALGAMATED BANK`, $17,000).
The command marks these records so a user cannot mistake an undisclosed payee for
a disclosed one — the difference between "they did not pay X" and "they may have
paid X through a wire whose payee the API does not carry."

### 8. Empty filtered result exits zero and says what it searched

Per the `cli-foundation` delta. The message names the filter and reports the size
and date span of the set that was searched, so the user can distinguish "no such
payment" from "no data for this period" — the difference between a finding and a
gap. Confirmed with the user before specifying.

## Risks / Trade-offs

- **`SearchTypeCategory=B` is an undocumented magic letter that OCPF could
  change** → The shape assertion in Decision 1 turns a silent semantic change
  into a loud failure. The constant and its meaning are recorded in `CLAUDE.md`
  and in a code comment citing the swagger URL.
- **A committee much larger than ~1,000 records makes the fetch-everything
  approach slow** → PageSize of 500–1000 keeps a statewide committee to a few
  requests. If a filer ever exceeds a threshold where this hurts, the params-dict
  fetch signature (Decision 2) allows pushing date bounds server-side without
  restructuring.
- **Local filtering can drift from what a user familiar with ocpf.us expects**
  → `--vendor` is specified as case-insensitive substring matching, so its
  behavior is defined by the spec and tested, rather than inherited from an
  undocumented endpoint.
- **The total will not match the filer's YTD expenditure figure** → Expected and
  explained in Non-Goals; worth a line in the command's help or README so a user
  comparing `ocpf filer` and `ocpf expenditures` is not misled.
- **The `cli-foundation` exit-code change is a real semantic change to a
  cross-cutting requirement** → It only narrows the non-zero case, and no
  existing command has a "filter matched nothing" path (`race` and `filer` treat
  an empty result as unresolvable input, which stays non-zero). Existing tests
  should be unaffected; if any assert non-zero on an empty *filtered* result,
  that assertion is what the change deliberately revises.

## Migration Plan

Purely additive apart from the internal move in Decision 4. No data migration, no
config change, no user-visible change to `race` or `filer`. The resolution move
lands first as its own commit so a regression in it is bisectable independently
of the new command.
