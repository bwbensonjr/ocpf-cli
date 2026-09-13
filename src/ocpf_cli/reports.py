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
and the only cross-filer path in the API. The per-filer path above deliberately
does not use it: its rows are built for a web table, and `reportingPeriod`
arrives in at least three incompatible shapes (`7/1/19 - 12/31/19`,
`9/1 - 9/30/2026` with no start year, and a bare `1/13/26` that is not a range),
while `reportList` returns the same filings with structured `startDate`,
`endDate` and integer `reportYear`. The two sources were verified to return
identical report sets (517 each for cpfId 14454).

The special-election sweep at the bottom of this module is the one place that
*must* use the log, because no other endpoint answers "which filers sought this
seat" — `reportList` cannot be queried without a cpfId, and the on-ballot and
legislative feeds carry no special elections at all. Two further properties of
the log shape that code:

5. The log's filters fail CLOSED, unlike `search/items`: an unknown
   `ReportTypeId` returns `[]` rather than the unfiltered database. So a
   mistyped filter here produces an empty answer, not a plausible wrong one.
6. The log returns a BARE LIST with no `summary`, so a short page is the only
   termination signal, and it has no server-side date or district filter —
   `StartIndex`, `PageSize`, `Name`, `CpfId`, `ReportTypeId` and
   `ReportTypeCategory` are the whole list. Year and district narrowing
   therefore happen locally, on the whole swept type.

The sweep parses `reportingPeriod` into real dates at the boundary and carries
neither the log's money nor its `amendmentDisplay` (literal HTML, `<br>Amendment`)
any further — see `SpecialReportRow`. That containment is the other half of the
warning above: the display-string parsing the log forces belongs to the log path
and must not be retrofitted onto the `reportList` rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import lru_cache
from typing import Any

from . import api, render

BASE_REPORT_TYPES_PATH = "reports/baseReportTypes/{cpf_id}"
REPORT_LIST_PATH = "reports/reportList/{cpf_id}"
REPORT_PATH = "report/{report_id}"
REPORT_LOG_PATH = "reports/log"

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


# --------------------------------------------------------------------------
# Cross-filer special-election sweep (`reports/log`)
# --------------------------------------------------------------------------

# `ReportTypeId` values for the two special-election filing stages. Both the
# depository and the non-depository spelling of a stage share one id:
# `Pre-Primary Report (Special)` and `Pre-primary Report (Special) (ND)` are
# both 22, so one id per stage covers both filing regimes. Verified live:
# type 22 returns 563 rows and type 23 returns 556, two requests each at
# PAGE_SIZE; an unknown id (99999) returns `[]` rather than the whole log.
SPECIAL_PRE_PRIMARY_TYPE_ID = 22
SPECIAL_PRE_ELECTION_TYPE_ID = 23


class SpecialStage(str, Enum):
    """Which stage of a special election a filing or request refers to.

    A `str` Enum so Typer can accept it as a `--stage` choice directly and the
    value round-trips into JSON output unchanged.
    """

    PRIMARY = "primary"
    GENERAL = "general"


# Report type id and the `reportTypeDescription` substring that identifies a
# stage's filing in a per-filer `reportList`. Matching on the description is a
# project-wide rule: the numeric `reportTypeId` is undocumented, and each stage
# has a depository and a non-depository spelling that differ only in case and a
# trailing `(ND)`, so a lowercased substring matches both.
STAGE_REPORT_TYPES: dict[SpecialStage, tuple[int, str]] = {
    SpecialStage.PRIMARY: (SPECIAL_PRE_PRIMARY_TYPE_ID, "pre-primary report (special)"),
    SpecialStage.GENERAL: (SPECIAL_PRE_ELECTION_TYPE_ID, "pre-election report (special)"),
}

# Two-digit years in the log are all 2000s: OCPF's earliest special-election
# filings are from 2003 and the field is not used for anything historical.
CENTURY = 2000


def _format_date(value: date) -> str:
    """Render a date the way OCPF writes one: `M/D/YYYY`, unpadded."""
    return f"{value.month}/{value.day}/{value.year}"


@dataclass(frozen=True)
class ReportingPeriod:
    """The window a filing covers, parsed out of the log's display string."""

    start: date
    end: date

    @property
    def label(self) -> str:
        """`7/27/2013 - 8/23/2013` — always four-digit years, unlike the source."""
        return f"{_format_date(self.start)} - {_format_date(self.end)}"


@dataclass(frozen=True)
class SpecialReportRow:
    """One special-election filing as the cross-filer log reports it.

    Deliberately carries neither money nor an amendment marker. The log returns
    every amendment generation of a filing — Steinhof (cpfId 15658) has four
    rows for the same 2013 pre-election window, at $9,940.00 as filed rising to
    $13,530.00 — so its totals identify a *version*, not a candidate's money.
    This row answers "who filed, for what seat, covering what window"; the money
    comes from the operative filing via `fetch_reports`.
    """

    cpf_id: int
    name: str
    office_sought: str
    period: ReportingPeriod | None
    report_id: int | None


def _parse_log_date(text: str, *, default_year: int | None = None) -> date | None:
    """Parse one side of a log `reportingPeriod`, e.g. `7/27/13` or `9/1`.

    A two-digit year is a 2000s year. A missing year (the `9/1 - 9/30/2026`
    shape) falls back to `default_year`, which the caller takes from the other
    end of the range.
    """
    parts = text.strip().split("/")
    if len(parts) == 2 and default_year is not None:
        parts = [*parts, str(default_year)]
    if len(parts) != 3:
        return None
    try:
        month, day, year = (int(part) for part in parts)
    except ValueError:
        return None
    if year < 100:
        year += CENTURY
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_reporting_period(value: Any) -> ReportingPeriod | None:
    """Parse a log `reportingPeriod` into real dates, or None if it is not a range.

    The log writes this field for a web table, so it arrives in several shapes.
    Returning None for anything that is not a parseable range is deliberate: a
    row whose window cannot be read cannot be placed in an election year, and
    guessing one would put a candidate in the wrong race.
    """
    if not isinstance(value, str):
        return None
    start_text, sep, end_text = value.partition("-")
    if not sep:
        # A bare date is not a range (`1/13/26`). No window, no year.
        return None
    end = _parse_log_date(end_text)
    if end is None:
        return None
    start = _parse_log_date(start_text, default_year=end.year)
    if start is None:
        return None
    return ReportingPeriod(start=start, end=end)


def _fetch_log_page(report_type_id: int, start_index: int) -> list[dict]:
    """Fetch one page of the report log for a report type."""
    params = {
        "ReportTypeId": report_type_id,
        # 1-based; `StartIndex=0` silently returns PAGE_SIZE-1 records here
        # rather than erroring. See point 2 in the module docstring.
        "StartIndex": start_index,
        "PageSize": PAGE_SIZE,
    }
    payload = api.get_json(REPORT_LOG_PATH, params=params)
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise api.OcpfApiError(
            "reports/log returned an unexpected response shape",
            path=REPORT_LOG_PATH,
        )
    return [row for row in payload if isinstance(row, dict)]


def fetch_report_log(report_type_id: int) -> list[dict]:
    """Fetch every log row for one report type, paging until the log is exhausted.

    The log returns a bare list with no `summary`, so a short page is the only
    signal that the last page has been read; `MAX_PAGES` keeps a pathological
    result set from pinning the CLI on the network.
    """
    collected: list[dict] = []

    for _ in range(MAX_PAGES):
        items = _fetch_log_page(report_type_id, START_INDEX_BASE + len(collected))
        if not items:
            break
        collected.extend(items)
        if len(items) < PAGE_SIZE:
            break
    else:
        raise api.OcpfApiError(
            f"reports/log did not finish paging after {MAX_PAGES} pages "
            f"({len(collected)} rows retrieved)",
            path=REPORT_LOG_PATH,
        )

    return collected


def _normalize_log_row(row: dict) -> SpecialReportRow | None:
    """Turn one raw log row into a `SpecialReportRow`, dropping the unusable."""
    cpf_id = row.get("cpfId")
    if not isinstance(cpf_id, int):
        return None
    office = " ".join((row.get("officeSought") or "").split())
    if not office:
        return None
    report_id = row.get("reportId")
    return SpecialReportRow(
        cpf_id=cpf_id,
        name=" ".join((row.get("fullNameReverse") or "").split()),
        office_sought=office,
        period=parse_reporting_period(row.get("reportingPeriod")),
        report_id=report_id if isinstance(report_id, int) else None,
    )


@lru_cache(maxsize=None)
def fetch_special_reports(stage: SpecialStage) -> tuple[SpecialReportRow, ...]:
    """Every special-election filing of one stage, across all filers.

    Memoized for the life of the process: the sweep is ~1,100 rows over two
    requests per stage and does not change within an invocation, so selecting a
    stage after probing for one must not refetch. Tests clear it with
    `fetch_special_reports.cache_clear()`.
    """
    report_type_id, _ = STAGE_REPORT_TYPES[stage]
    rows = (_normalize_log_row(row) for row in fetch_report_log(report_type_id))
    return tuple(row for row in rows if row is not None)


def find_stage_report(reports: list[dict], stage: SpecialStage, year: int) -> dict | None:
    """The operative filing of `stage` in `year` among a filer's reports.

    `reports` comes from `fetch_reports`, which defaults to `OnlyCurrent=true`,
    so a filing that was amended appears once here — as its latest version, with
    the amended totals. Matching is on `reportTypeDescription` rather than the
    undocumented numeric id, which also makes one substring cover a stage's
    depository and non-depository spellings.
    """
    _, description = STAGE_REPORT_TYPES[stage]
    matches = [
        report
        for report in reports
        if description in (report.get("reportTypeDescription") or "").lower()
        and (report.get("endDateValue") or report.get("startDateValue")) is not None
        and (report.get("endDateValue") or report.get("startDateValue")).year == year
    ]
    if not matches:
        return None
    # More than one survives only if a filer filed twice for the stage in one
    # year; the latest window is the one the summary is about.
    return max(matches, key=lambda r: r.get("endDateValue") or r.get("startDateValue"))
