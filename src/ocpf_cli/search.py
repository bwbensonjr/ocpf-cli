"""Client for the OCPF `search/items` endpoint (report line items).

`search/items` returns the individual records inside filed reports —
contributions received, expenditures made, subvendor payments. Its full
parameter list is published at `https://api.ocpf.us/swagger/v1/swagger.json`
(29 query parameters); the project's own endpoint notes list only the route.

Three properties of this endpoint make it dangerous to call casually, and each
is why this module exists rather than commands calling `api.get_json` directly:

1. `SearchTypeCategory` selects which kind of record you get, and an
   *unrecognized* value silently returns RECEIPTS. `E`, `expenditures`, `EXP`
   and `""` all fall back that way — no error, no warning, just a plausible
   table of money flowing the wrong direction. The category is therefore a
   module constant here, never built from user input, and `fetch_expenditures`
   additionally verifies the shape of what came back.
2. `StartIndex` is 1-BASED, not 0-based: `StartIndex=0` and `StartIndex=1`
   both return the first record. Paging from a 0-based offset silently
   re-fetches the record on each page boundary — a duplicate that inflates any
   total computed from the result. Verified against the live API.
3. A misnamed filter parameter is ignored rather than rejected. `Name` filters
   the counterparty and works; `VendorName` is in the swagger spec but is inert
   — passing it returns the entire unfiltered database (~1.8M records). An
   ignored filter is indistinguishable from one that matched everything, so
   this module pages the filer's full record set and lets callers filter
   locally.

Response shape: `{"summary": {count, total, totalDisplay, description},
"items": [...]}`. `summary` is null unless `withSummary=true` is passed.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from . import api, render

SEARCH_ITEMS_PATH = "search/items"

# SearchTypeCategory codes. Verified against the live API; see the module
# docstring for the silent-fallback hazard that makes these constants rather
# than user-supplied strings.
CATEGORY_EXPENDITURES = "B"
CATEGORY_RECEIPTS = "R"
CATEGORY_SUBVENDOR = "S"

# `StartIndex` is a 1-BASED record offset; see point 2 in the module docstring.
# Named so a reader who assumes 0-based indexing does not "fix" it.
START_INDEX_BASE = 1

# Records per request. A committee's full expenditure history is typically
# ~1,000 records, so this keeps most filers to one or two calls.
PAGE_SIZE = 1000

# Guard against a pathological result set pinning the CLI on the network.
MAX_PAGES = 100


def _parse_date(value: Any) -> date | None:
    """Parse OCPF's `M/D/YYYY` date string. Unparseable input yields None."""
    return render.parse_date(value)


def _looks_like_receipt(item: dict) -> bool:
    """True if `item` has the shape of a contribution rather than an expenditure.

    Receipt records carry a contributor (`contributorCpfId`/`fullNameReverse`)
    and no `vendor` key; expenditure records carry `vendor`. Used to catch the
    silent `SearchTypeCategory` fallback described in the module docstring.
    """
    if "vendor" in item:
        return False
    return "contributorCpfId" in item or "fullNameReverse" in item


def _fetch_page(params: dict[str, Any], start_index: int) -> tuple[list[dict], int | None]:
    """Fetch one page; return its items and the reported total record count."""
    page_params = dict(params)
    # 1-based; see the module docstring. Callers pass a 1-based position.
    page_params["StartIndex"] = start_index
    page_params["PageSize"] = PAGE_SIZE
    page_params["withSummary"] = "true"

    payload = api.get_json(SEARCH_ITEMS_PATH, params=page_params)
    if not isinstance(payload, dict):
        raise api.OcpfApiError(
            "search/items returned an unexpected response shape",
            path=SEARCH_ITEMS_PATH,
        )

    items = payload.get("items") or []
    if not isinstance(items, list):
        raise api.OcpfApiError(
            "search/items returned a non-list 'items' field",
            path=SEARCH_ITEMS_PATH,
        )

    summary = payload.get("summary")
    expected = summary.get("count") if isinstance(summary, dict) else None
    return items, expected


def fetch_items(params: dict[str, Any]) -> list[dict]:
    """Fetch every record matching `params`, paging until the set is complete.

    Pages on `StartIndex`/`PageSize` and compares the accumulated count against
    the `summary.count` the API reports for the same query. A shortfall raises
    `OcpfApiError` rather than returning a partial set: a silently truncated
    result understates a total, which for campaign-finance data is worse than
    an error, because the wrong answer still looks like an answer.
    """
    collected: list[dict] = []
    expected: int | None = None

    for _ in range(MAX_PAGES):
        items, page_expected = _fetch_page(params, START_INDEX_BASE + len(collected))
        if page_expected is not None:
            expected = page_expected

        if not items:
            # No progress. Either we have everything, or the API stalled; the
            # completeness check below decides which.
            break

        collected.extend(items)

        if expected is not None and len(collected) >= expected:
            break

        if len(items) < PAGE_SIZE:
            # A short page is the last page. This is the only termination
            # condition when the API omits `summary`, and a cheap guard against
            # an extra round trip when it does not.
            break
    else:
        raise api.OcpfApiError(
            f"search/items did not finish paging after {MAX_PAGES} pages "
            f"({len(collected)} records retrieved)",
            path=SEARCH_ITEMS_PATH,
        )

    if expected is not None and len(collected) < expected:
        raise api.OcpfApiError(
            f"search/items returned {len(collected)} records but reported "
            f"{expected}; refusing to report an incomplete total",
            path=SEARCH_ITEMS_PATH,
        )

    if expected is not None and len(collected) > expected:
        # More records than the API says exist means the page offsets overlapped
        # — the 1-based `StartIndex` trap. Duplicates inflate a total just as
        # silently as a short read deflates one, so fail rather than report it.
        raise api.OcpfApiError(
            f"search/items returned {len(collected)} records but reported only "
            f"{expected}; page offsets overlapped, refusing to report an "
            f"inflated total",
            path=SEARCH_ITEMS_PATH,
        )

    return collected


def annotate(items: list[dict]) -> list[dict]:
    """Attach parsed numeric `amountValue` and `dateValue` to each record.

    OCPF returns `amount` as a display string (`"$1,234.56"`) and `date` as
    `M/D/YYYY`. Parsing once at the boundary keeps filtering, summing and
    grouping on real numbers and dates; formatting happens only when rendering.
    """
    for item in items:
        item["amountValue"] = render.parse_currency(item.get("amount"))
        item["dateValue"] = _parse_date(item.get("date"))
    return items


def fetch_expenditures(cpf_id: int) -> list[dict]:
    """Fetch every expenditure record for `cpf_id`, annotated and verified.

    Raises `OcpfApiError` if the response contains receipt-shaped records,
    which is how the silent `SearchTypeCategory` fallback would surface.
    """
    items = fetch_items(
        {
            "CpfId": cpf_id,
            "SearchTypeCategory": CATEGORY_EXPENDITURES,
        }
    )

    if any(_looks_like_receipt(item) for item in items):
        raise api.OcpfApiError(
            "search/items returned contribution records for an expenditure "
            "query; refusing to report money received as money spent",
            path=SEARCH_ITEMS_PATH,
        )

    return annotate(items)


def format_api_date(value: date) -> str:
    """Format a date the way this API's date parameters expect: `M/D/YYYY`."""
    return f"{value.month}/{value.day}/{value.year}"


def fetch_summary(
    params: dict[str, Any],
    *,
    start: date | None = None,
    end: date | None = None,
) -> tuple[dict, dict | None]:
    """Fetch the API's own count and total for the filtered set, in one request.

    `summary` describes the WHOLE filtered set rather than the returned page, so
    a `PageSize` of 1 answers a scalar question at the cost of one request and
    one record. That record is not waste: it is the evidence that the filter was
    applied.

    When `start`/`end` are given, the sample record's date is checked against
    them. This is the guard that makes a summary-only fetch safe on an endpoint
    where an unrecognized filter parameter is ignored rather than rejected (see
    point 3 in the module docstring) — an ignored date bound would return the
    filer's entire history with a plausible, larger total and no error at all.
    One in-window record does not prove every counted record is in-window, but it
    turns the likely failure from a wrong number into a raised error.
    """
    page_params = dict(params)
    page_params["StartIndex"] = START_INDEX_BASE
    page_params["PageSize"] = 1
    page_params["withSummary"] = "true"

    payload = api.get_json(SEARCH_ITEMS_PATH, params=page_params)
    if not isinstance(payload, dict):
        raise api.OcpfApiError(
            "search/items returned an unexpected response shape",
            path=SEARCH_ITEMS_PATH,
        )

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        # Without a summary there is no total. Returning zero here would be a
        # confident wrong answer; the caller asked for a figure, not a guess.
        raise api.OcpfApiError(
            "search/items returned no summary; refusing to report a total",
            path=SEARCH_ITEMS_PATH,
        )

    items = payload.get("items") or []
    sample = items[0] if isinstance(items, list) and items else None

    if sample is not None and (start is not None or end is not None):
        when = _parse_date(sample.get("date"))
        outside = when is not None and (
            (start is not None and when < start) or (end is not None and when > end)
        )
        if outside:
            raise api.OcpfApiError(
                f"search/items returned a record dated {sample.get('date')} for a "
                f"query bounded to {start}..{end}; the date filter was not "
                f"applied, refusing to report a total over an unknown period",
                path=SEARCH_ITEMS_PATH,
            )

    return summary, sample


def fetch_category_total(
    cpf_id: int,
    category: str,
    start: date,
    end: date,
) -> tuple[int, float]:
    """Return `(count, total)` for one filer, one record kind, one closed window.

    `category` must be one of the module's `CATEGORY_*` constants, never a
    user-supplied string: an unrecognized `SearchTypeCategory` silently returns
    receipts (point 1 in the module docstring). When expenditures were asked for,
    the sample record is shape-checked as a second line of defense, so a
    mis-wired constant fails loudly rather than reporting money received as money
    paid.
    """
    if category not in (CATEGORY_RECEIPTS, CATEGORY_EXPENDITURES, CATEGORY_SUBVENDOR):
        raise ValueError(f"unknown search category {category!r}")

    summary, sample = fetch_summary(
        {
            "CpfId": cpf_id,
            "SearchTypeCategory": category,
            "StartDate": format_api_date(start),
            "EndDate": format_api_date(end),
        },
        start=start,
        end=end,
    )

    if (
        category == CATEGORY_EXPENDITURES
        and sample is not None
        and _looks_like_receipt(sample)
    ):
        raise api.OcpfApiError(
            "search/items returned contribution records for an expenditure "
            "query; refusing to report money received as money spent",
            path=SEARCH_ITEMS_PATH,
        )

    count = summary.get("count") or 0
    total = render.parse_currency(summary.get("total"))
    return int(count), total
