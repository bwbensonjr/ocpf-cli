"""`ocpf filer` — profile, YTD finances, and recent reports for one filer.

Pipeline: resolve the argument to a `cpfId` (a bare integer is used directly; a
name is matched against the legislative field for the year) -> fetch
`filer/payload/{cpfId}` in one call -> render the profile, YTD line, and recent
filing log (or JSON).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import typer

from .. import api, render
from ..legislative import fetch_merged_field

FILER_PAYLOAD_PATH = "filer/payload/{cpf_id}"


@dataclass(frozen=True)
class FilerMatch:
    """A candidate name match from the legislative field."""

    cpf_id: int
    name: str
    office: str


class FilerResolutionError(Exception):
    """Name resolution failed. `matches` is populated for the ambiguous case."""

    def __init__(self, message: str, *, matches: list[FilerMatch] | None = None) -> None:
        super().__init__(message)
        self.matches = matches or []


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for forgiving name matching."""
    return " ".join(text.lower().split())


def resolve_filer(query: str, year: int) -> int:
    """Resolve `query` to a single `cpfId`.

    A bare integer is used directly (works for any filer type). Otherwise the
    value is matched case-insensitively against `filerName` in the legislative
    field for `year`; ambiguity is never guessed away.
    """
    stripped = query.strip()
    if stripped.lstrip("-").isdigit():
        return int(stripped)

    target = _normalize(query)
    field = fetch_merged_field(year)
    matches = [
        FilerMatch(
            cpf_id=row.get("cpfId"),
            name=row.get("filerName", ""),
            office=row.get("officeSought", ""),
        )
        for row in field
        if target in _normalize(row.get("filerName", ""))
    ]

    if len(matches) == 1:
        return matches[0].cpf_id
    if len(matches) == 0:
        raise FilerResolutionError(
            f'"{query}" matches no legislative filer for {year}; '
            f"pass a numeric cpfId directly to look up any filer"
        )
    raise FilerResolutionError(
        f'"{query}" matches more than one legislative filer',
        matches=matches,
    )


def fetch_filer_payload(cpf_id: int) -> dict:
    """Fetch `filer/payload/{cpfId}`; raise on an unknown/invalid cpfId.

    OCPF returns HTTP 400 for an out-of-range cpfId; we translate that into a
    clear "no filer found" error rather than a bare HTTP message.
    """
    try:
        payload = api.get_json(FILER_PAYLOAD_PATH.format(cpf_id=cpf_id))
    except api.OcpfApiError as exc:
        if exc.status_code == 400:
            raise FilerResolutionError(f"No filer found for cpfId {cpf_id}") from exc
        raise

    if not isinstance(payload, dict) or not payload.get("filer"):
        raise FilerResolutionError(f"No filer found for cpfId {cpf_id}")
    return payload


def _office_str(value: Any) -> str:
    """Render an office field that may be a string or a nested object."""
    if isinstance(value, dict):
        return value.get("officeDistrict") or value.get("display") or ""
    return value or ""


def _render_summary(payload: dict) -> None:
    """Print the human-readable profile, YTD line, and recent-reports table."""
    filer = payload.get("filer", {})

    name = filer.get("fullNameReverse") or filer.get("fullName") or ""
    print(f"Filer:      {name}  (cpfId {filer.get('cpfId')})")
    if filer.get("committeeName"):
        print(f"Committee:  {filer.get('committeeName')}")
    party = filer.get("partyAffiliation") or "-"
    acct = filer.get("accountType", {}).get("description", "")
    print(f"Party:      {party}" + (f"    Type: {acct}" if acct else ""))

    office = _office_str(filer.get("officeSoughtDescription") or filer.get("officeSought"))
    if office:
        print(f"Office:     {office}")
    held = _office_str(filer.get("officeHeld"))
    if held and held != office:
        print(f"Holds:      {held}")

    if filer.get("isActive") and not filer.get("closedDate"):
        status = "active"
    else:
        status = "closed"
        if filer.get("closedDate"):
            status += f" ({filer.get('closedDate')})"
    print(f"Status:     {status}")
    if filer.get("organizationDate"):
        print(f"Organized:  {filer.get('organizationDate')}")

    treasurer = filer.get("treasurer") or {}
    if isinstance(treasurer, dict) and treasurer.get("fullName"):
        print(f"Treasurer:  {treasurer.get('fullName')}")

    # Year-to-date finances (single cumulative figure, never split by election).
    ytd = payload.get("ytdReport") or {}
    print()
    if ytd:
        as_of = ytd.get("bankReportEndDate")
        suffix = f" (as of {as_of})" if as_of else ""
        print(f"Year-to-date{suffix}:")
        print(f"  Raised YTD:    {render.format_currency(ytd.get('receiptsYtdNumeric'))}")
        print(f"  Spent YTD:     {render.format_currency(ytd.get('expendituresYtdNumeric'))}")
        print(f"  Cash on Hand:  {render.format_currency(ytd.get('currentCashOnHandNumeric'))}")
    else:
        print("Year-to-date: no current summary on file")

    # Recent filing log.
    logs = payload.get("logReports") or []
    print()
    if not logs:
        print("Recent reports: none found")
        return
    print("Recent reports:")
    rows = [
        [
            log.get("reportTypeDescription", ""),
            log.get("reportingPeriod", ""),
            log.get("dateFiledHeader", "") or log.get("dateFiled", ""),
            log.get("receiptTotal", ""),
            log.get("expenditureTotal", ""),
        ]
        for log in logs
    ]
    headers = ["Type", "Period", "Filed", "Receipts", "Expenditures"]
    print(render.render_table(rows, headers, right_align=[3, 4]))


def filer(
    filer: str = typer.Argument(
        ..., help="Numeric cpfId, or a candidate name (legislative filers)"
    ),
    year: int = typer.Option(
        None, "--year", help="Year for name resolution / YTD context (default: current)"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit the filer profile, YTD, and reports as JSON"
    ),
) -> None:
    """Profile, year-to-date finances, and recent reports for a single filer."""
    if year is None:
        year = date.today().year

    try:
        cpf_id = resolve_filer(filer, year)
    except FilerResolutionError as exc:
        render.error(str(exc))
        for m in exc.matches:
            render.status(f"  {m.cpf_id}  {m.name}  ({m.office})")
        raise typer.Exit(code=1)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    try:
        payload = fetch_filer_payload(cpf_id)
    except FilerResolutionError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    if json_output:
        render.emit_json(
            {
                "filer": payload.get("filer"),
                "ytdReport": payload.get("ytdReport"),
                "logReports": payload.get("logReports"),
            }
        )
    else:
        _render_summary(payload)
