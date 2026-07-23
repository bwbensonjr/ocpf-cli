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
    fetch_merged_field,
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
    return row.get("districtCodeHeld") == code


def _sort_key(row: dict) -> Any:
    # Order by receipts descending (biggest fundraiser first), then name.
    return (-(row.get("receiptsYtdNumeric") or 0), row.get("filerName", ""))


def _render_table(district: District, rows: list[dict], timeline: Timeline) -> None:
    """Print the human-readable summary header and table to stdout."""
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
        table_rows.append(
            [
                row.get("filerName", ""),
                row.get("partyAffiliation", "") or "-",
                incumbent,
                render.format_currency(row.get("receiptsYtdNumeric")),
                render.format_currency(row.get("expendituresYtdNumeric")),
                render.format_currency(row.get("currentCashOnHandNumeric")),
            ]
        )

    headers = [
        "Candidate",
        "Party",
        "Inc",
        "Raised YTD",
        "Spent YTD",
        "Cash on Hand",
    ]
    print(
        render.render_table(
            table_rows, headers, right_align=[3, 4, 5]
        )
    )
    print()
    print("* incumbent (holds this seat)")
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
        _render_table(resolved, matched, timeline)
