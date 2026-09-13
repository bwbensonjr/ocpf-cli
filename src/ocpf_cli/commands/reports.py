"""`ocpf reports` and `ocpf report` — a filer's filings, and one filing in full.

Two commands share this module rather than taking one file each. Adjacent
modules named `report.py` and `reports.py` are a maintenance hazard out of
proportion to the convention they would satisfy, and the two commands share the
report-type vocabulary, the schedule names, and the row coercion.

`ocpf reports <filer>` is the index: resolve the argument to a cpfId (shared
with `ocpf filer`), fetch every report that filer has filed, filter locally,
render. `ocpf report <report-id>` is the filing itself — the data behind the
OCPF web UI's DisplayReport page.

Filtering is local rather than pushed into the API, for the reason `search.py`
gives: filter parameters on this API are silently ignored when they are not
understood, and an ignored filter looks exactly like one that matched
everything. See `reports.py` for the endpoint hazards behind both commands.
"""

from __future__ import annotations

import sys
from datetime import date
from typing import Any

import typer

from .. import api, render, reports as reports_api
from ..resolve import FilerResolutionError, resolve_filer

# User-facing schedule names -> the report payload's field names. The mapping
# is explicit so an unrecognized name can be rejected with the valid list
# rather than silently rendering nothing.
SCHEDULES: dict[str, str] = {
    "receipts": "receipts",
    "expenditures": "expenditures",
    "out-of-pocket": "oopExpenditures",
    "in-kind": "inkindContributions",
    "liabilities": "liabilities",
    "subvendor": "subvendorPayments",
}


def _counterparty(item: dict) -> str:
    """The other party to a line item, whichever shape the schedule uses.

    Report schedules name the counterparty differently by schedule and by
    filing regime: `fullNameReverse` for contributors and creditors, `vendor`
    for some expenditure rows. `clarifiedName` is OCPF's own resolution of an
    opaque payee and is preferred when present — it is authoritative, unlike
    any inference from the raw string.
    """
    for key in ("clarifiedName", "vendor", "fullNameReverse", "name"):
        value = (item.get(key) or "").strip()
        if value:
            return value
    return ""


def _purpose(item: dict) -> str:
    return (item.get("clarifiedPurpose") or item.get("description") or item.get("purpose") or "").strip()


def _amendment_marker(row: dict) -> str:
    """Short marker for a row's amendment status, blank when neither applies."""
    if row.get("isAmendment"):
        return "amend"
    if row.get("isAmended"):
        return "amended"
    return ""


def filter_reports(
    rows: list[dict],
    *,
    year: int | None = None,
    report_type: str | None = None,
    since: date | None = None,
    until: date | None = None,
) -> list[dict]:
    """Narrow `rows` by the user's filters. Conditions combine conjunctively.

    Date bounds test the reporting period for OVERLAP with the window, not
    containment: `--since 2013-03-01` keeps a filing covering 2/16-3/15 because
    the question a date bound answers is "which filing covers this date", and a
    containment test would hide exactly that filing.
    """
    needle = report_type.strip().lower() if report_type else None
    result = []

    for row in rows:
        start = row.get("startDateValue")
        end = row.get("endDateValue")

        if year is not None:
            row_year = row.get("reportYear")
            if row_year is not None:
                if row_year != year:
                    continue
            elif not _period_touches_year(start, end, year):
                continue
        if since is not None and (end or start) is not None and (end or start) < since:
            continue
        if until is not None and (start or end) is not None and (start or end) > until:
            continue
        if needle is not None:
            if needle not in (row.get("reportTypeDescription") or "").lower():
                continue
        result.append(row)

    return result


def _period_touches_year(start: date | None, end: date | None, year: int) -> bool:
    if start is not None and start.year == year:
        return True
    if end is not None and end.year == year:
        return True
    if start is not None and end is not None:
        return start.year <= year <= end.year
    return False


def _sort_key(row: dict) -> tuple:
    """Most recent filing first; report id breaks ties deterministically."""
    filed = row.get("dateFiledValue") or date.min
    return (filed, row.get("reportId") or 0)


def _describe_filters(
    year: int | None,
    report_type: str | None,
    since: date | None,
    until: date | None,
) -> str:
    parts = []
    if report_type:
        parts.append(f'type "{report_type}"')
    if year is not None:
        parts.append(f"year {year}")
    if since is not None:
        parts.append(f"since {since.isoformat()}")
    if until is not None:
        parts.append(f"until {until.isoformat()}")
    return ", ".join(parts)


def _year_span(rows: list[dict]) -> str:
    """Human description of the years `rows` covers, for the no-match line."""
    years = sorted({r["reportYear"] for r in rows if r.get("reportYear")})
    if not years:
        return "no dated reports"
    if years[0] == years[-1]:
        return str(years[0])
    return f"{years[0]}-{years[-1]}"


def _json_report_row(row: dict) -> dict[str, Any]:
    """One listing row as JSON: numeric money alongside the filed display string."""
    return {
        "reportId": row.get("reportId"),
        "reportType": row.get("reportTypeDescription"),
        "reportTypeId": row.get("reportTypeId"),
        "reportingPeriod": row.get("reportingPeriod"),
        "startDate": row.get("startDate"),
        "endDate": row.get("endDate"),
        "reportYear": row.get("reportYear"),
        "dateFiled": row.get("dateFiledDisplay"),
        "receiptTotal": row.get("receiptTotal"),
        "receiptTotalValue": row.get("receiptTotalValue"),
        "expenditureTotal": row.get("expenditureTotal"),
        "expenditureTotalValue": row.get("expenditureTotalValue"),
        "startBalance": row.get("startBalance"),
        "startBalanceValue": row.get("startBalanceValue"),
        "endBalance": row.get("endBalance"),
        "endBalanceValue": row.get("endBalanceValue"),
        "isAmendment": bool(row.get("isAmendment")),
        "isAmended": bool(row.get("isAmended")),
        "previousReportId": row.get("previousReportId") or None,
        "baseReportTypeDescription": row.get("baseReportTypeDescription"),
        "reportLink": row.get("ocpfUsReportLink"),
    }


def reports(
    filer: str = typer.Argument(
        ..., help="Numeric cpfId, or a candidate name (legislative filers)"
    ),
    year: int = typer.Option(None, "--year", help="Only reports for this reporting year"),
    report_type: str = typer.Option(
        None,
        "--type",
        help='Only report types containing this text, e.g. "pre-election"',
    ),
    since: str = typer.Option(
        None, "--since", help="Only periods ending on/after this date (YYYY-MM-DD)"
    ),
    until: str = typer.Option(
        None, "--until", help="Only periods starting on/before this date (YYYY-MM-DD)"
    ),
    limit: int = typer.Option(None, "--limit", help="Cap the rows displayed"),
    include_superseded: bool = typer.Option(
        False,
        "--include-superseded",
        help="Also list versions replaced by a later amendment",
    ),
    resolve_year: int = typer.Option(
        None,
        "--resolve-year",
        help="Year used to resolve a candidate name (default: current)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit the reports as JSON"),
) -> None:
    """List the reports a filer has filed, most recent first.

    Covers the filer's whole filing history. Narrow a long listing with --type
    ("pre-election", "year-end"), --year, or --limit.
    """
    from .expenditures import parse_date_option

    try:
        since_date = parse_date_option(since, "--since")
        until_date = parse_date_option(until, "--until")
    except ValueError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    # The resolution year is about matching a NAME against a legislative field,
    # not about which reports to list: the listing always covers every year the
    # filer has filed in, which is what makes a 2013 special-election filing
    # reachable at all.
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
        rows = reports_api.fetch_reports(cpf_id, include_superseded=include_superseded)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    # No reports at all is a dead end, not a finding: exit non-zero.
    if not rows:
        message = f"No reports on file for cpfId {cpf_id}"
        if filer.strip().lstrip("-").isdigit():
            # `reports` and `report` are one character apart; say so rather
            # than leave the user to spot it.
            message += f"; if that was a report id, use `ocpf report {filer.strip()}`"
        render.error(message)
        raise typer.Exit(code=1)

    matched = filter_reports(
        rows,
        year=year,
        report_type=report_type,
        since=since_date,
        until=until_date,
    )

    # A filter matching nothing is an answer, not a failure: stdout, exit zero.
    if not matched:
        described = _describe_filters(year, report_type, since_date, until_date)
        if json_output:
            render.emit_json(
                {
                    "filerCpfId": cpf_id,
                    "filters": described,
                    "searchedReports": len(rows),
                    "searchedSpan": _year_span(rows),
                    "reportCount": 0,
                    "reports": [],
                }
            )
        else:
            suffix = f" matching {described}" if described else ""
            print(f"No reports{suffix}")
            print(f"(searched {len(rows):,} reports, {_year_span(rows)})")
        return

    ordered = sorted(matched, key=_sort_key, reverse=True)

    if json_output:
        render.emit_json(
            {
                "filerCpfId": cpf_id,
                "reportCount": len(ordered),
                "includesSuperseded": include_superseded,
                "reports": [_json_report_row(row) for row in ordered],
            }
        )
        return

    shown = ordered[:limit] if limit is not None else ordered
    table = [
        [
            row.get("reportId"),
            row.get("reportTypeDescription") or "",
            row.get("reportingPeriod") or "",
            row.get("dateFiledDisplay") or "",
            render.format_currency(row.get("receiptTotalValue")),
            render.format_currency(row.get("expenditureTotalValue")),
            _amendment_marker(row),
        ]
        for row in shown
    ]
    headers = ["Report", "Type", "Period", "Filed", "Receipts", "Expenditures", "Amd"]
    print(render.render_table(table, headers, right_align=[4, 5]))
    print()
    if limit is not None and len(ordered) > limit:
        print(f"Showing {len(shown)} of {len(ordered)} reports (--limit {limit}).")
    print(f"{len(ordered)} reports")
    if not include_superseded:
        # Commentary goes to stderr; flush stdout first or the unbuffered
        # stderr line lands above the table in a terminal.
        sys.stdout.flush()
        render.status(
            "Showing current filings only; --include-superseded adds versions "
            "replaced by a later amendment."
        )


def _render_schedule(name: str, items: list[dict]) -> None:
    """Print one schedule as a labeled section, or say it is empty."""
    print()
    print(f"{name.upper()}")
    if not items:
        print(f"  (no {name} recorded in this report)")
        return
    rows = [
        [
            item.get("date") or "",
            render.format_currency(render.parse_currency(item.get("amount"))),
            _counterparty(item),
            _purpose(item),
            item.get("recordTypeDescription") or "",
        ]
        for item in items
    ]
    print(render.render_table(rows, ["Date", "Amount", "Name", "Purpose", "Type"], right_align=[1]))
    total = sum(render.parse_currency(i.get("amount")) for i in items)
    print(f"  {len(items)} items, {render.format_currency(total)}")


def _totals_pairs(report: dict) -> list[tuple[str, str]]:
    """The filing's schedule totals, in the order the CPF 102 presents them."""
    return [
        ("Start balance", report.get("startBalance") or ""),
        ("Receipts (itemized)", report.get("receiptItemizedTotal") or ""),
        ("Receipts (unitemized)", report.get("receiptUnitemizedTotal") or ""),
        ("Receipts (total)", report.get("receiptTotal") or ""),
        ("Expenditures (itemized)", report.get("expenditureItemizedTotal") or ""),
        ("Expenditures (unitemized)", report.get("expenditureUnitemizedTotal") or ""),
        ("Expenditures (total)", report.get("expenditureTotal") or ""),
        ("Out-of-pocket", report.get("oopExpenditureTotal") or ""),
        ("In-kind", report.get("inkindTotal") or ""),
        ("Liabilities", report.get("liabilityItemizedTotal") or ""),
        ("End balance", report.get("endBalance") or ""),
    ]


def report(
    report_id: str = typer.Argument(..., help="Numeric report id, e.g. 170378"),
    schedule: list[str] = typer.Option(
        None,
        "--schedule",
        help=f"Also print a schedule's line items ({', '.join(SCHEDULES)}). Repeatable.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit the report as JSON"),
) -> None:
    """Show one filed report: header, schedule totals, and requested schedules.

    The PDF of the filing is at `report/pdf/<id>` on the OCPF API; the report's
    web link is printed below.
    """
    raw = report_id.strip()
    if not raw.lstrip("-").isdigit():
        render.error(
            f'"{raw}" is not a report id — did you mean `ocpf reports {raw}`?'
        )
        raise typer.Exit(code=1)

    requested = list(schedule or [])
    unknown = [name for name in requested if name not in SCHEDULES]
    if unknown:
        render.error(
            f"unknown schedule {unknown[0]!r}; valid names are "
            f"{', '.join(SCHEDULES)}"
        )
        raise typer.Exit(code=1)

    try:
        payload = reports_api.fetch_report(int(raw))
    except reports_api.ReportNotFoundError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    if json_output:
        out = _json_report_row(payload)
        out.update(
            {
                "committeeName": payload.get("committeeName"),
                "candidateName": payload.get("candidateFullNameReverse"),
                "officeDistrictSought": payload.get("officeDistrictSought"),
                "treasurer": _treasurer(payload),
                "bankName": payload.get("bankName"),
                "nextReportId": payload.get("nextReportId") or None,
                "totals": {label: value for label, value in _totals_pairs(payload)},
            }
        )
        for name in requested:
            out.setdefault("schedules", {})[name] = payload.get(SCHEDULES[name]) or []
        render.emit_json(out)
        return

    _render_report_header(payload)
    print()
    pairs = [[label, value] for label, value in _totals_pairs(payload) if value]
    print(render.render_table(pairs, ["", "Amount"], right_align=[1]))

    for name in requested:
        _render_schedule(name, payload.get(SCHEDULES[name]) or [])

    link = payload.get("ocpfUsReportLink")
    if link:
        print()
        print(link)


def _treasurer(payload: dict) -> str:
    first = (payload.get("treasurerFirstName") or "").strip()
    last = (payload.get("treasurerLastName") or "").strip()
    return " ".join(part for part in (first, last) if part)


def _render_report_header(payload: dict) -> None:
    """Print the filing's identifying header."""
    fields = [
        ("Report", payload.get("reportId")),
        ("Type", payload.get("reportTypeDescription")),
        ("Period", payload.get("reportingPeriod")),
        ("Filed", payload.get("dateFiledDisplay")),
        ("Committee", payload.get("committeeName")),
        ("Candidate", payload.get("candidateFullNameReverse")),
        ("Office", payload.get("officeDistrictSought")),
        ("Treasurer", _treasurer(payload)),
        ("Bank", payload.get("bankName")),
    ]

    marker = _amendment_lineage(payload)
    if marker:
        fields.append(("Amendment", marker))

    width = max(len(label) for label, _ in fields)
    for label, value in fields:
        if value:
            print(f"{label.ljust(width)}  {value}")


def _amendment_lineage(payload: dict) -> str:
    """Describe the filing's amendment relationships, or '' when it has none."""
    parts = []
    if payload.get("isAmendment"):
        previous = payload.get("previousReportId")
        parts.append(f"amends report {previous}" if previous else "is an amendment")
    if payload.get("isAmended"):
        following = payload.get("nextReportId")
        parts.append(
            f"amended by report {following}" if following else "has been amended"
        )
    return "; ".join(parts)
