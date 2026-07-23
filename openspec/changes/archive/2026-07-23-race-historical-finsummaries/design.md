## Context

`ocpf race` resolves a district, fetches the current-cycle legislative feeds
(`reports/legislative/depository/ytd/{year}` + the non-depository race feed),
merges them by `cpfId`, filters by district code, and renders a YTD table with an
as-of date derived from `bankReportEndDate`. These feeds are only populated from
~2020 onward; for earlier years the district resolves and a couple of names may
leak through, but the money columns are blank.

Investigation confirmed the historical money lives in
`onballot/finsummaries/{year}/{districtCode}`, which is populated through the
2018 cycle and empty from 2020 on — the mirror image of the current feeds. It is
district-scoped by URL, so it needs no client-side district filter. Its shape
differs from the current feeds:

```
current feed row                     finsummaries row
────────────────                     ────────────────
receiptsYtdNumeric      (number)     receipts      "$63,727.50"  (string)
expendituresYtdNumeric  (number)     expenditures  "$54,831.01"  (string)
currentCashOnHandNumeric(number)     endBalance    "$8,896.49"   (string)
districtCodeSought/Held (int)        districtCode: 0  (always)
bankReportEndDate  "M/D/YYYY"        (none)
                                     isIncumbent (bool), isWinner (bool)
```

## Goals / Non-Goals

**Goals:**
- Make `ocpf race --year <old-year>` show real money for pre-2020 races.
- Reuse the existing sort, currency formatting, and `--json` machinery by
  normalizing historical rows into the shared row shape.
- Be honest about semantics: historical numbers are final full-cycle totals, not
  a YTD snapshot, so label and header them accordingly.

**Non-Goals:**
- No change to current-year behavior or output.
- No attempt to reconcile the messy overlap years (e.g. 2016) into a single
  merged view — fallback-on-empty picks one source per query.
- No new endpoints beyond `onballot/finsummaries`.

## Decisions

### Source selection: fallback-on-empty, not a year cutoff

Run the existing pipeline (`fetch_merged_field` → `filter_by_district`) first.
If no matched row has money (all of `receiptsYtdNumeric`/`expendituresYtdNumeric`
/`currentCashOnHandNumeric` absent or zero across matches), fetch
`finsummaries` for the resolved code and switch to the historical path.

- **Why:** the current/historical boundary is not a clean year (2016 had rows in
  both feeds); "does the current feed actually have money?" is the real signal.
- **Alternative — hard `year < 2020` cutoff:** simpler but brittle at the
  boundary and wrong for districts that lag the general pattern. Rejected.
- **Alternative — always merge both:** doubles API calls on every current-year
  query for no benefit. Rejected.

### Normalization into the shared row shape

Add a `finsummaries` fetch + normalizer in `legislative.py` that maps each row to
a dict carrying `filerName`, `partyAffiliation`, the three numeric money fields
(parsed from the currency strings), `isIncumbent`, and `isWinner`. Rendering,
sorting (`_sort_key` by `receiptsYtdNumeric`), and `--json` then work unchanged.

- Currency parsing strips `$` and `,` and parses to float; blank/`"$0.00"` → 0.0.
- A `render.parse_currency` helper (inverse of `format_currency`) is the natural
  home if one does not already exist.

### Rendering: a mode flag drives header + columns

The renderer learns whether it is showing historical data (e.g. a `historical`
bool or a source enum threaded from the command). Historical mode: omit the
as-of line, relabel money columns to `Raised` / `Spent` / `End Bal`, and insert a
`Won` column from `isWinner`. Incumbent marker uses `isIncumbent` rather than
`districtCodeHeld == code`.

- **Why a flag over two separate renderers:** the header, sort, currency
  formatting, and JSON paths are identical; only three presentation details
  differ. A flag keeps them in one place.

### Timeline in historical mode

`build_timeline` still fetches `filingSchedules/{year}` for primary/general
dates (available for old years). With no `bankReportEndDate`, `as_of_date` is
`None` and `lagging_filers` is empty — the renderer already guards on those, so
the as-of line and lagging note naturally drop out.

## Risks / Trade-offs

- **[Fallback trigger misfires if a current-year district legitimately has zero
  money]** → In practice current-cycle districts with candidates have nonzero
  receipts; a genuinely empty current district would trigger a `finsummaries`
  call that also returns nothing, ending in the existing "no candidates found"
  error. Acceptable.
- **[`finsummaries` currency format drift]** → Parser tolerates `$`, commas, and
  empty/zero strings; anything unparseable falls back to 0.0 rather than
  crashing. Covered by tests.
- **[Extra API call on historical queries]** → One additional request only when
  the current feeds come back empty. Negligible.

## Migration Plan

Additive change; no data migration. Current-year output is byte-for-byte
unchanged (the fallback only triggers when current feeds are empty). Rollback is
reverting the change.

## Open Questions

None outstanding — source selection (fallback-on-empty), final-totals relabeling,
and the winner marker were settled during exploration.
