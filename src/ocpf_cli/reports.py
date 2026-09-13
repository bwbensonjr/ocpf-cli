"""Client for the OCPF report endpoints (filed reports and their schedules).

A "report" here is a filing — the CPF 102 a committee actually submitted for a
reporting period, with its schedule totals and line items. This is the data
behind the OCPF web UI's `Reports/DisplayReport?id=N` page.

Four properties of these endpoints are why this module exists rather than
commands calling `api.get_json` directly. Each was verified against the live
API (cpfId 14819 Matewsky, cpfId 14454 Brownsberger, report 170378):

1. `reports/reportList/{cpfId}` REQUIRES `BaseReportTypeId`. Without it the
   endpoint returns HTTP 400 ("No base report type ID was provided"), which is
   why the project's endpoint notes long listed it as broken. It takes exactly
   one value: a comma-separated `3,8` returns an empty body, and a repeated
   parameter silently uses the first. A complete listing therefore means asking
   `reports/baseReportTypes/{cpfId}` what types a filer has and calling the list
   endpoint once per type — seven calls for a twenty-year depository committee,
   one for a non-depository committee.
2. `StartIndex` is 1-BASED and is a record offset, not a page number. Pages
   start at 1, 1+PageSize, 1+2*PageSize. `StartIndex=0` returns HTTP 500 here
   (on `reports/log` it silently returns PageSize-1 records instead), and
   consecutive offsets return overlapping windows: with PageSize=3, offset 1
   gives records 1-3 and offset 2 gives records 2-4. Paging from a 0-based
   offset therefore either errors or silently duplicates.
3. `OnlyCurrent` defaults to TRUE, so the default listing omits superseded
   versions of amended filings. For cpfId 14819 base type 8: 21 reports by
   default, 47 with `OnlyCurrent=false`.
4. `report/{reportId}` has NO 404. An id below 39 returns HTTP 400; a
   well-formed id that does not exist returns HTTP 500 with an empty body. Both
   mean "no such report", and `fetch_report` translates them into
   `ReportNotFoundError` so a caller can tell a missing report from an outage.

`reports/log` is the other way into this data — one request, every report type,
and the only cross-filer path in the API. It is deliberately not used here: its
rows are built for a web table, and `reportingPeriod` arrives in at least three
incompatible shapes (`7/1/19 - 12/31/19`, `9/1 - 9/30/2026` with no start year,
and a bare `1/13/26` that is not a range), while `reportList` returns the same
filings with structured `startDate`, `endDate` and integer `reportYear`. The two
sources were verified to return identical report sets (517 each for cpfId
14454). Cross-filer work needs the log and will have to parse those formats;
confine that to the log path rather than retrofitting it onto these rows.
"""

from __future__ import annotations

from typing import Any

from . import api, render

BASE_REPORT_TYPES_PATH = "reports/baseReportTypes/{cpf_id}"
REPORT_LIST_PATH = "reports/reportList/{cpf_id}"
REPORT_PATH = "report/{report_id}"

# `StartIndex` is a 1-BASED record offset. This is a named constant rather than
# a literal 1 because a reader who assumes 0-based indexing will "fix" it, and
# the failure is HTTP 500 on this endpoint and silent duplication on siblings.
# See point 2 in the module docstring.
START_INDEX_BASE = 1

# Reports per request. The largest single base report type observed is 330
# (cpfId 14454 deposit reports), so this keeps every observed filer to one call
# per type while still paging correctly if one exceeds it.
PAGE_SIZE = 500

# Guard against a pathological result set pinning the CLI on the network.
MAX_PAGES = 100

# `report/{reportId}` returns HTTP 400 below this id rather than a not-found
# status. Rejecting locally avoids spending a round trip on a certain failure.
MIN_REPORT_ID = 39


class ReportNotFoundError(Exception):
    """No report exists for the requested id.

    Distinct from `OcpfApiError` so a caller can tell "this report does not
    exist" from "OCPF is unreachable", which the API's status codes do not.
    """

    def __init__(self, message: str, *, report_id: int) -> None:
        super().__init__(message)
        self.report_id = report_id


def fetch_base_report_types(cpf_id: int) -> list[dict]:
    """Return the base report types `cpf_id` has filed under.

    An empty list means the filer has filed nothing (cpfId 96054 is one such).
    That is an empty result, not an error: the caller decides what to say about
    a filer with no reports.
    """
    path = BASE_REPORT_TYPES_PATH.format(cpf_id=cpf_id)
    payload = api.get_json(path)
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise api.OcpfApiError(
            "reports/baseReportTypes returned an unexpected response shape",
            path=path,
        )
    return [row for row in payload if isinstance(row, dict)]


def _fetch_list_page(
    cpf_id: int,
    base_type_id: Any,
    start_index: int,
    *,
    only_current: bool,
) -> tuple[list[dict], int | None]:
    """Fetch one page of a base type's reports; return items and reported count."""
    path = REPORT_LIST_PATH.format(cpf_id=cpf_id)
    params = {
        "BaseReportTypeId": base_type_id,
        # 1-based; see the module docstring. Callers pass a 1-based position.
        "StartIndex": start_index,
        "PageSize": PAGE_SIZE,
        "OnlyCurrent": "true" if only_current else "false",
        "withSummary": "true",
    }

    payload = api.get_json(path, params=params)
    if not isinstance(payload, dict):
        raise api.OcpfApiError(
            "reports/reportList returned an unexpected response shape",
            path=path,
        )

    items = payload.get("items") or []
    if not isinstance(items, list):
        raise api.OcpfApiError(
            "reports/reportList returned a non-list 'items' field",
            path=path,
        )

    summary = payload.get("summary")
    expected = summary.get("count") if isinstance(summary, dict) else None
    return items, expected


def fetch_report_list(
    cpf_id: int,
    base_type_id: Any,
    *,
    only_current: bool = True,
) -> list[dict]:
    """Fetch every report of one base type for `cpf_id`, paging until complete.

    Pages on the 1-based `StartIndex` and compares the accumulated count against
    the `summary.count` the API reports. A shortfall raises rather than
    returning a partial set: a listing that silently omits a filing is worse
    than an error, because the gap is invisible.
    """
    path = REPORT_LIST_PATH.format(cpf_id=cpf_id)
    collected: list[dict] = []
    expected: int | None = None

    for _ in range(MAX_PAGES):
        items, page_expected = _fetch_list_page(
            cpf_id,
            base_type_id,
            START_INDEX_BASE + len(collected),
            only_current=only_current,
        )
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
            # A short page is the last page — the only termination condition
            # when the API omits `summary`.
            break
    else:
        raise api.OcpfApiError(
            f"reports/reportList did not finish paging after {MAX_PAGES} pages "
            f"({len(collected)} reports retrieved)",
            path=path,
        )

    if expected is not None and len(collected) < expected:
        raise api.OcpfApiError(
            f"reports/reportList returned {len(collected)} reports but reported "
            f"{expected}; refusing to report an incomplete listing",
            path=path,
        )

    return collected


def fetch_reports(cpf_id: int, *, include_superseded: bool = False) -> list[dict]:
    """Fetch every report `cpf_id` has filed, across all base report types.

    Fans out over `fetch_base_report_types` and merges. Because a bad page
    offset on this endpoint produces plausible duplicated rows rather than an
    error (see the module docstring), the merged result is checked for a
    repeated `reportId` and raises rather than rendering an inflated listing.
    """
    types = fetch_base_report_types(cpf_id)
    merged: list[dict] = []
    seen: set[Any] = set()

    for base_type in types:
        base_type_id = base_type.get("baseReportTypeId")
        if base_type_id is None:
            continue
        rows = fetch_report_list(
            cpf_id,
            base_type_id,
            only_current=not include_superseded,
        )
        for row in rows:
            report_id = row.get("reportId")
            if report_id is not None and report_id in seen:
                raise api.OcpfApiError(
                    f"reports/reportList returned report {report_id} more than "
                    f"once for cpfId {cpf_id}; page offsets overlapped, "
                    f"refusing to report a duplicated listing",
                    path=REPORT_LIST_PATH.format(cpf_id=cpf_id),
                )
            if report_id is not None:
                seen.add(report_id)
            row["baseReportTypeId"] = base_type_id
            row["baseReportTypeDescription"] = base_type.get("baseReportTypeDescription")
            merged.append(row)

    return annotate(merged)


def annotate(rows: list[dict]) -> list[dict]:
    """Attach parsed numbers and dates to each report row.

    Every monetary field on these endpoints is a display string (`"$1,430.30"`)
    and every date is `M/D/YYYY`. Parsing once at the boundary keeps sorting,
    filtering and JSON output on real types; formatting happens only at render.
    """
    for row in rows:
        row["startDateValue"] = render.parse_date(row.get("startDate"))
        row["endDateValue"] = render.parse_date(row.get("endDate"))
        row["dateFiledValue"] = render.parse_date(row.get("dateFiledDisplay"))
        row["receiptTotalValue"] = render.parse_currency(row.get("receiptTotal"))
        row["expenditureTotalValue"] = render.parse_currency(row.get("expenditureTotal"))
        row["startBalanceValue"] = render.parse_currency(row.get("startBalance"))
        row["endBalanceValue"] = render.parse_currency(row.get("endBalance"))
    return rows


def fetch_report(report_id: int) -> dict:
    """Fetch one filed report in full, including its schedule line items.

    Raises `ReportNotFoundError` for an id that identifies no filing — both the
    HTTP 400 the API returns below `MIN_REPORT_ID` and the HTTP 500 it returns
    for a well-formed id that does not exist. Network failures, timeouts and
    every other status stay `OcpfApiError`, so a genuine outage still surfaces
    as one.
    """
    path = REPORT_PATH.format(report_id=report_id)

    if report_id < MIN_REPORT_ID:
        # Deterministic: the API rejects these outright, so do not spend a
        # round trip discovering it.
        raise ReportNotFoundError(
            f"no report {report_id}: report ids start at {MIN_REPORT_ID}",
            report_id=report_id,
        )

    try:
        payload = api.get_json(path)
    except api.OcpfApiError as exc:
        if exc.status_code in (400, 500):
            # The API has no 404. Both of these mean "no report by that id" —
            # worded so it does not claim more than it knows.
            raise ReportNotFoundError(
                f"no report {report_id}: the OCPF API returned no report for "
                f"that id",
                report_id=report_id,
            ) from exc
        raise

    if not isinstance(payload, dict):
        raise api.OcpfApiError(
            "report returned an unexpected response shape",
            path=path,
        )

    return annotate([payload])[0]
