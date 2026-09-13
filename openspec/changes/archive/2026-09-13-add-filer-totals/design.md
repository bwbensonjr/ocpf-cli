## Context

See proposal.md — Why. Constraints that shape the approach, verified against the
live API (cpfId 14902):

- **The API answers this question itself.** `search/items` with
  `withSummary=true` returns `{"summary": {count, total, totalDisplay,
  description}, "items": [...]}` where `summary` describes the *whole filtered
  set*, not the page. `PageSize=1` therefore costs one request and one record.
- **`StartDate` and `EndDate` work**, take `M/D/YYYY`, are inclusive, and
  compose with `CpfId`. A window crossing a year boundary is fine
  (11/1/2023-10/25/2024 returns 1,760 receipts, $581,434.45). Coverage goes back
  to at least 2010.
- **But a filter this API does not understand is ignored, not rejected.** This is
  documented in `search.py` for `VendorName`, which silently returns the entire
  1.8M-record database. `StartDate`/`EndDate` are real parameters today; the
  hazard is that an ignored bound is indistinguishable from one that matched
  everything, and here the consequence is a *bigger* number rather than an
  error. Bounded to 2024, cpfId 14902 gives count 1,277 with a first record dated
  6/24/2024; unbounded, count 15,411 with a first record dated 5/1/2009.
- **`SearchTypeCategory` fails open to receipts** for any unrecognized value —
  `E`, `expenditures`, `EXP`, `""` all return contributions. `search.py` already
  holds `CATEGORY_RECEIPTS`/`CATEGORY_EXPENDITURES` constants and a
  receipt-shape detector for exactly this reason.
- **Existing seams**: `search.fetch_items` pages a full record set and
  `search.annotate` coerces it; neither is what this command needs.
  `resolve.resolve_filer`, `render.format_currency`, `render.emit_json` are
  reused as-is.

## Goals / Non-Goals

**Goals:**

- A scalar answer in one request, with the window inseparable from the figure.
- The two fail-open hazards on this endpoint made unreachable rather than
  documented: the category cannot be user-supplied, and the date bound is
  verified to have been applied.

**Non-Goals:**

- Replacing `ocpf expenditures`. That command exists to show *which* payments;
  this one answers *how much*, and does not enumerate.
- Matching `ocpf filer`'s YTD figure. Different quantities by construction.
- Batching, caching, or a multi-filer interface. See the proposal.

## Decisions

### 1. Summary-only fetch, not paged-and-summed

Add `fetch_summary(params)` to `search.py` beside `fetch_items`: it sends
`PageSize=1`, `StartIndex=1` (the 1-based base the module already documents) and
`withSummary=true`, and returns the summary plus the single sample record.

*Alternative considered*: reusing `fetch_items` to retrieve every record in the
window and summing `amountValue` locally, as `ocpf expenditures` does. Rejected
on cost without a correctness gain — ~1,800 records over two round trips to
reproduce a number the API computed in one. The consumer needs a few thousand of
these; the difference is hours.

*Consequence*: the command's correctness now rests entirely on the server-side
date filter, which is why Decision 2 exists. `ocpf expenditures` deliberately
filters locally *because* server-side filters fail open; this command cannot,
so it verifies instead.

### 2. The date bound is verified, not trusted

The same request that returns the summary returns one record. That record's date
is checked against the requested window, and a record outside it raises
`OcpfApiError` rather than reporting the figure.

This is cheap (no extra request), and it catches the exact failure that matters:
a silently ignored bound returns the filer's whole history with a plausible,
larger total. It is not a proof — one in-window record does not establish that
every counted record is in-window — and the spec says only that an out-of-window
record is detected. It converts the most likely failure from a wrong number into
an error, which is the same bargain `search.py` already strikes with its
receipt-shape assertion.

*Alternative considered*: a second, unbounded request to compare counts. Rejected:
it doubles the request count for every call to detect a regression that a single
sample already catches, and for a filer whose entire history falls inside the
window the two counts are legitimately equal, so it yields false alarms.

### 3. Category is an enum at the CLI boundary

`--category` is a Typer enum of `receipts`/`expenditures`, mapped to
`search.CATEGORY_RECEIPTS`/`CATEGORY_EXPENDITURES` through a dict. Typer rejects
anything else before any code runs, so no user string can reach
`SearchTypeCategory`. The sample record is additionally checked with the
existing `_looks_like_receipt` helper when expenditures were requested, which
catches the silent fallback if the constant is ever mis-wired.

### 4. Both bounds required, and echoed

`--start` and `--end` are required options, not optional ones defaulting to the
year. An unbounded total is exactly the figure this change exists to displace,
so the command should not be able to produce one by omission. The rendered
output and the JSON both carry the window.

Dates accept `YYYY-MM-DD` and OCPF's `M/D/YYYY` via the existing
`parse_date_option` helper in `commands/expenditures.py`; that helper moves to a
shared module rather than being imported across command modules, following the
precedent set when filer resolution moved to `resolve.py`.

### 5. An empty window is a finding, not a failure

A window with no records reports `$0.00` over 0 records and exits zero. This is
the `cli-foundation` filter-matches-nothing contract: the filer was resolved and
the query succeeded, and "they raised nothing in this window" is an answer a
consumer needs to be able to receive. An unresolvable filer or a failed request
stays non-zero.

## Risks / Trade-offs

- **The whole figure depends on a server-side filter** → Decision 2 verifies the
  bound was applied on every call. Residual risk is a partially-applied filter,
  which no cheap check can exclude.
- **`summary.total` is trusted as computed** → The command reports the API's own
  arithmetic rather than re-deriving it. That is the point (Decision 1), but it
  means an OCPF-side error in the summary is invisible here. Mitigated by
  reporting `count` alongside `total` so an implausible figure is at least
  inspectable, and by `ocpf expenditures` remaining available to enumerate the
  same window.
- **`--start`/`--end` differ in meaning from `ocpf expenditures`'
  `--since`/`--until`** → Different names for different semantics is deliberate:
  these are required bounds defining the measurement, not optional narrowing
  filters. The help text says so.

## Open Questions

None.
