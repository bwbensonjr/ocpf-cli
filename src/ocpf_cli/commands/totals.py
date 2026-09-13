"""`ocpf totals` — what a filer raised or spent between two dates.

The figure the feeds publish is a full calendar year, so fetched after a cycle
it includes money raised *after* the election. For cpfId 14902 in 2020, 70% of
the year's receipts arrived after October 31. Post-election money follows the
outcome, so treating the published figure as pre-election money is wrong in the
direction that flatters the result.

Both bounds are required and the window is echoed back with the figure: an
unbounded total is precisely the ambiguous number this command exists to
replace, so it should not be producible by omission.

Unlike `ocpf expenditures`, which pages a filer's records and filters locally,
this asks the API for its own count and total over the filtered set — one
request instead of two and ~1,800 records. That trade puts the answer's
correctness on a server-side date filter, and on this API an unrecognized filter
is ignored rather than rejected, so `search.fetch_summary` verifies the bound
was applied before any figure is reported.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

import typer

from .. import api, render, search
from ..options import parse_date_option
from ..resolve import FilerResolutionError, resolve_filer


class Category(str, Enum):
    """The kinds of money this command can total.

    An enum rather than a free string because the value it selects,
    `SearchTypeCategory`, silently returns receipts for anything it does not
    recognize. Typer rejects an unknown value before any request is made, so a
    typo cannot become a plausible wrong answer.
    """

    receipts = "receipts"
    expenditures = "expenditures"


# User-facing name -> the API constant. Defined in `search.py`, never built from
# user input.
CATEGORY_CODES = {
    Category.receipts: search.CATEGORY_RECEIPTS,
    Category.expenditures: search.CATEGORY_EXPENDITURES,
}


def totals(
    filer: str = typer.Argument(
        ..., help="Numeric cpfId, or a candidate name (legislative filers)"
    ),
    start: str = typer.Option(
        ..., "--start", help="First day of the window (YYYY-MM-DD), inclusive"
    ),
    end: str = typer.Option(
        ..., "--end", help="Last day of the window (YYYY-MM-DD), inclusive"
    ),
    category: Category = typer.Option(
        Category.receipts, "--category", help="Money received or money paid"
    ),
    resolve_year: int = typer.Option(
        None,
        "--resolve-year",
        help="Year used to resolve a candidate name (default: current)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit the total as JSON"),
) -> None:
    """Total what a filer received or paid between two dates.

    Both bounds are required, and the window is reported with the figure. Use
    this rather than a year-to-date number when you need pre-election money:
    a calendar-year figure includes everything raised after the election.
    """
    try:
        start_date = parse_date_option(start, "--start")
        end_date = parse_date_option(end, "--end")
    except ValueError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    if start_date > end_date:
        render.error(
            f"--start {start_date.isoformat()} is after --end {end_date.isoformat()}; "
            f"the window is inverted"
        )
        raise typer.Exit(code=1)

    name_year = resolve_year or date.today().year

    try:
        cpf_id = resolve_filer(filer, name_year)
    except FilerResolutionError as exc:
        render.error(str(exc))
        for match in exc.matches:
            render.status(f"  {match.cpf_id}  {match.name}  ({match.office})")
        raise typer.Exit(code=1)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    try:
        count, total = search.fetch_category_total(
            cpf_id, CATEGORY_CODES[category], start_date, end_date
        )
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    if json_output:
        render.emit_json(
            {
                "filerCpfId": cpf_id,
                "category": category.value,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "recordCount": count,
                "total": total,
                "totalDisplay": render.format_currency(total),
            }
        )
        return

    # A label/value block rather than a table: there is one record here, and a
    # table of one row wants a header it has no use for.
    fields = [
        ("cpfId", str(cpf_id)),
        ("Category", category.value),
        ("Window", f"{start_date.isoformat()} to {end_date.isoformat()}"),
        ("Records", f"{count:,}"),
        ("Total", render.format_currency(total)),
    ]
    width = max(len(label) for label, _ in fields)
    for label, value in fields:
        print(f"{label.ljust(width)}  {value}")

    # A window with no records is an answer ("they raised nothing then"), not a
    # failure: it is reported on stdout above and the command exits zero.
