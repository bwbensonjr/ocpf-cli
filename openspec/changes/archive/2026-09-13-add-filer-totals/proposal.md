## Why

There is no way to ask what a committee raised or spent **between two dates**.
`ocpf race` and `ocpf filer` report the year-to-date figure the feeds publish,
and `ocpf expenditures` returns line items a caller must total themselves.

Fetched after a cycle, the published "year to date" figure is a **full calendar
year**, so it includes money raised *after* the election. For cpfId 14902,
measured against the live API:

| Year | Through 10/31 | Full year | Raised after 10/31 |
|---|---|---|---|
| 2024 | $401,190.59 | $560,090.46 | 28% |
| 2020 | $32,935.00 | $111,125.63 | 70% |

Post-election money follows the outcome — winners raise, losers stop — so any
analysis that treats the published figure as pre-election money is wrong in the
direction that flatters the result. A model regressing margin on money would be
fitting partly on the thing it is trying to predict.

The endpoint already computes the answer. `search/items` with `CpfId`,
`StartDate`, `EndDate` and `withSummary=true` returns the count and total for
the whole filtered set in a **single request**, no paging, verified working back
to 2010 and across year boundaries:

```
GET search/items?SearchTypeCategory=R&CpfId=14902
    &StartDate=11/1/2023&EndDate=10/25/2024&PageSize=1&StartIndex=1&withSummary=true
-> {"summary": {"count": 1760, "total": 581434.45, "totalDisplay": "$581,434.45"}}
```

`SearchTypeCategory=B` gives expenditures for the same window: 845 items,
$397,182.30.

## What Changes

- Add the command
  `ocpf totals <filer> --start <date> --end <date> [--category receipts|expenditures] [--resolve-year <year>] [--json]`,
  which reports the record count and total amount a single committee received or
  paid over an explicit closed window.
- **Both bounds are required.** A window-less total is the ambiguous figure this
  change exists to replace, and the output **echoes the window back**, so a
  figure is never reported without the dates it covers.
- `--category` defaults to `receipts` and accepts `receipts` or `expenditures`.
  The CLI value is mapped through an enum to the `SearchTypeCategory` constants
  already in `search.py`; **the user's string never reaches the API parameter**,
  because an unrecognized value there silently returns receipts.
- Fetch as a **single summary request** (`PageSize=1`, `withSummary=true`) rather
  than paging the filer's records and summing locally. The API computes the
  total server-side over the filtered set; retrieving ~1,800 records to add them
  up would be slower and no more correct.
- Guard the server-side filter, which is the one thing this approach depends on.
  A filter parameter this API does not understand is ignored rather than
  rejected, and an ignored date bound returns the filer's entire history looking
  exactly like a valid answer. The single record the request returns alongside
  the summary is checked to fall inside the requested window — a cheap,
  request-free assertion that the bound was applied. (Unbounded, the same query
  returns count 15,411 with a first record dated 5/1/2009; bounded to 2024, count
  1,277 with a first record dated 6/24/2024.)
- Reuse `resolve.resolve_filer` so `ocpf totals 14902` and `ocpf totals <name>`
  behave as they do for every other filer-scoped command.

Out of scope, deliberately:

- **Subvendor and donation categories** (`S`, `D`). The enum makes them a
  one-line addition when something needs them; neither has a caller today.
- **Multi-filer or multi-window batch output.** The consumer needs a few
  thousand of these, but that is a matter of calling the command in a loop or
  using `--json`; a batch interface is a different command with a different
  result shape.
- **Caching.** The consumer will want it for a few thousand calls, but a cache
  belongs to whatever drives the loop, not to a read-only CLI whose correctness
  depends on returning what the API currently says.
- **Reconciling the total against `ocpf filer`'s YTD figure.** They legitimately
  differ: item search includes out-of-pocket candidate expenditures the YTD bank
  figure excludes. This is documented in `expenditure-search` already.

## Capabilities

### New Capabilities
- `filer-totals`: The `ocpf totals` command — the required closed window, the
  category selection and its fail-open guard, the single-request summary
  retrieval, the echoed window, and `--json`.

### Modified Capabilities

None. `cli-foundation` already covers the exit-code and output contracts, and no
existing command's behavior changes.

## Impact

- **New code**: a summary-fetch function in `src/ocpf_cli/search.py` beside
  `fetch_items` (same endpoint, same hazards, same module), and
  `src/ocpf_cli/commands/totals.py`; the subcommand registered in `cli.py`.
- **Reused foundation**: `api.get_json` / `OcpfApiError`, `resolve.resolve_filer`,
  `render` for currency and JSON, and the `CATEGORY_*` constants `search.py`
  already defines.
- **External API**: exactly one GET per invocation.
- **Docs**: `README.md` gains the command; `CLAUDE.md`'s `search/items` section
  gains the verified fact that `StartDate`/`EndDate` work and that
  `withSummary=true` answers a scalar question without paging.
- **No breaking changes**: purely additive.

## Related

Closes bwbensonjr/ocpf-cli#2. Independent of #3 and #4 — it touches no spec
those changes modify, so it can proceed in parallel with either.
