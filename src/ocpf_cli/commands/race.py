"""`ocpf race` — YTD financial summary for a legislative district's candidates.

Pipeline: resolve the district -> fetch and merge the depository + non-depository
legislative feeds -> filter to the district -> add timeline context (election
dates, as-of date) -> render a table (or JSON).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import typer

from .. import api, render
from ..districts import DistrictResolutionError, District, resolve_district
from ..legislative import (
    DEPOSITORY_PATH,
    NON_DEPOSITORY_PATH,
    fetch_finsummaries,
    fetch_merged_field,
    has_money,
    normalize_finsummaries,
    reports_of,
)

# Backwards-compatible alias: the merge helpers now live in `legislative`.
_reports_of = reports_of


def filter_by_district(rows: list[dict], code: int) -> list[dict]:
    """Keep rows sought-for or held-in the given district code."""
    return [
        row
        for row in rows
        if row.get("districtCodeSought") == code
        or row.get("districtCodeHeld") == code
    ]


def _parse_report_date(value: str | None) -> tuple[int, int, int] | None:
    """Parse an `M/D/YYYY` OCPF date into a sortable `(y, m, d)` tuple."""
    if not value:
        return None
    parts = value.split("/")
    if len(parts) != 3:
        return None
    try:
        month, day, year = (int(p) for p in parts)
    except ValueError:
        return None
    return (year, month, day)


@dataclass
class Timeline:
    """Timeline context for the summary header."""

    primary_election_date: str | None
    general_election_date: str | None
    as_of_date: str | None
    lagging_filers: list[str]


def build_timeline(year: int, rows: list[dict]) -> Timeline:
    """Fetch election dates and derive the as-of date from the matched rows.

    The as-of date is the latest `bankReportEndDate` present; any row whose
    date lags behind that is flagged so comparisons aren't silently uneven.
    """
    schedule = api.get_json(f"filingSchedules/{year}")
    primary = schedule.get("primaryElectionDate") if isinstance(schedule, dict) else None
    general = schedule.get("generalElectionDate") if isinstance(schedule, dict) else None

    dated = [
        (row, _parse_report_date(row.get("bankReportEndDate")))
        for row in rows
    ]
    present = [(row, d) for row, d in dated if d is not None]

    as_of_date: str | None = None
    lagging: list[str] = []
    if present:
        latest = max(d for _, d in present)
        as_of_row = next(row for row, d in present if d == latest)
        as_of_date = as_of_row.get("bankReportEndDate")
        lagging = [
            row.get("filerName", "")
            for row, d in present
            if d != latest
        ]

    return Timeline(
        primary_election_date=primary,
        general_election_date=general,
        as_of_date=as_of_date,
        lagging_filers=lagging,
    )


def _is_incumbent(row: dict, code: int) -> bool:
    # Historical (finsummaries) rows carry an explicit flag and a districtCode of
    # 0, so they can't be matched on districtCodeHeld; current-cycle rows use the
    # held-code comparison.
    if "isIncumbent" in row:
        return bool(row["isIncumbent"])
    return row.get("districtCodeHeld") == code


def _sort_key(row: dict) -> Any:
    # Order by receipts descending (biggest fundraiser first), then name.
    return (-(row.get("receiptsYtdNumeric") or 0), row.get("filerName", ""))


def _render_table(
    district: District,
    rows: list[dict],
    timeline: Timeline,
    historical: bool = False,
) -> None:
    """Print the human-readable summary header and table to stdout.

    Current-cycle data renders as a YTD snapshot with an as-of date. Historical
    (finsummaries) data renders as final full-cycle totals: no as-of line,
    final-total column labels, and a winner marker.
    """
    print(f"District:  {district.label} (code {district.code})")
    dates = []
    if timeline.primary_election_date:
        dates.append(f"primary {timeline.primary_election_date}")
    if timeline.general_election_date:
        dates.append(f"general {timeline.general_election_date}")
    if dates:
        print(f"Election:  {', '.join(dates)}")
    if timeline.as_of_date:
        print(f"As of:     {timeline.as_of_date} (year-to-date, cumulative)")
    print()

    ordered = sorted(rows, key=_sort_key)
    table_rows = []
    for row in ordered:
        incumbent = "*" if _is_incumbent(row, district.code) else ""
        money = [
            render.format_currency(row.get("receiptsYtdNumeric")),
            render.format_currency(row.get("expendituresYtdNumeric")),
            render.format_currency(row.get("currentCashOnHandNumeric")),
        ]
        base = [
            row.get("filerName", ""),
            row.get("partyAffiliation", "") or "-",
            incumbent,
        ]
        if historical:
            won = "W" if row.get("isWinner") else ""
            table_rows.append(base + [won] + money)
        else:
            table_rows.append(base + money)

    if historical:
        headers = ["Candidate", "Party", "Inc", "Won", "Raised", "Spent", "End Bal"]
        right_align = [4, 5, 6]
    else:
        headers = [
            "Candidate",
            "Party",
            "Inc",
            "Raised YTD",
            "Spent YTD",
            "Cash on Hand",
        ]
        right_align = [3, 4, 5]
    print(render.render_table(table_rows, headers, right_align=right_align))
    print()
    print("* incumbent (holds this seat)")
    # Only explain the winner marker when at least one candidate carries it;
    # OCPF's isWinner is unset for some historical races (e.g. unopposed).
    if historical and any(row.get("isWinner") for row in rows):
        print("W won the general election")
    if timeline.lagging_filers:
        names = ", ".join(timeline.lagging_filers)
        render.status(
            f"note: figures for {names} are as of an earlier report than "
            f"{timeline.as_of_date}"
        )


def race(
    district: str = typer.Argument(
        ..., help="District name (e.g. 'Suffolk and Middlesex') or numeric code"
    ),
    year: int = typer.Option(
        None, "--year", help="Election/filing year (defaults to the current year)"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit merged candidate records as JSON"
    ),
) -> None:
    """Year-to-date financial summary of the candidates in a legislative district."""
    if year is None:
        # Avoid importing datetime at module load; current year is a runtime fact.
        from datetime import date

        year = date.today().year

    try:
        resolved = resolve_district(district)
    except DistrictResolutionError as exc:
        render.error(str(exc))
        for cand in exc.candidates:
            render.status(f"  {cand.code}  {cand.label}")
        raise typer.Exit(code=1)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    try:
        merged = fetch_merged_field(year)
        matched = filter_by_district(merged, resolved.code)
        historical = False
        # The current-cycle feeds only carry money from ~2020 on. For earlier
        # cycles they resolve names but leave the money blank, so fall back to
        # the district-scoped historical summaries (final full-cycle totals).
        if not has_money(matched):
            hist_rows = normalize_finsummaries(
                fetch_finsummaries(year, resolved.code)
            )
            if hist_rows:
                matched = hist_rows
                historical = True
        if not matched:
            render.error(
                f"No candidates found for {resolved.label} (code "
                f"{resolved.code}) in {year}"
            )
            raise typer.Exit(code=1)
        timeline = build_timeline(year, matched)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    if json_output:
        render.emit_json(sorted(matched, key=_sort_key))
    else:
        _render_table(resolved, matched, timeline, historical=historical)
