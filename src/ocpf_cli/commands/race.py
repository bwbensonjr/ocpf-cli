"""`ocpf race` — financial summary for a legislative district's candidates.

Regular cycle (the default): resolve the district -> fetch and merge the
depository + non-depository legislative feeds -> filter to the district -> add
timeline context (election dates, as-of date) -> render a table (or JSON).

Special elections (`--special`): the feeds above carry none, so the roster comes
from the filings instead. Resolve the district -> sweep `reports/log` for the
special report types -> keep the rows whose office and reporting-period year
match -> pick the stage -> read each candidate's money from their *operative*
filing, never from the sweep rows -> render.

The two paths are separate on purpose. `--special` branches before the
legislative-feed fetch, so the regular path runs the code and issues the
requests it did before this option existed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import typer

from .. import api, render, reports
from ..districts import (
    DistrictResolutionError,
    District,
    _normalize,
    _parse_office_sought,
    resolve_district,
)
from ..reports import ReportingPeriod, SpecialReportRow, SpecialStage
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


def filter_by_district(rows: list[dict], code: int | None) -> list[dict]:
    """Keep rows sought-for or held-in the given district code.

    A district resolved without a code matches nothing. The guard is not
    defensive padding: `row.get(...)` returns None for a row whose own code is
    absent, so a plain `== code` comparison against a None code would match
    every such row and report unrelated candidates as this district's field.
    """
    if code is None:
        return []
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
    if code is None:
        return False
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
    print(f"District:  {district.full_label}")
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


# --------------------------------------------------------------------------
# Special elections
# --------------------------------------------------------------------------

# What a candidate's money reads as when they filed nothing operative for the
# stage. Distinct from "$0.00", which would assert they raised nothing.
NOT_REPORTED = "not reported"


@dataclass(frozen=True)
class SpecialCandidate:
    """One candidate on a special-election roster, with their filed money.

    `report` is the operative filing the figures came from, or None when the
    candidate filed nothing for this stage — the case `NOT_REPORTED` renders.
    """

    cpf_id: int
    name: str
    report: dict | None

    @property
    def receipts(self) -> float | None:
        return None if self.report is None else self.report.get("receiptTotalValue")

    @property
    def expenditures(self) -> float | None:
        return None if self.report is None else self.report.get("expenditureTotalValue")


class SpecialRaceError(Exception):
    """No usable special election for the request.

    Separate from `OcpfApiError` so the command can tell "this district held no
    such special election" — a statement about the data — from an outage.
    """


def _rows_for_district(district: District, year: int, stage: SpecialStage) -> list[SpecialReportRow]:
    """Sweep rows for one stage that belong to `district` in `year`.

    Matching is on the exact normalized district description, never a substring:
    `"1st Suffolk"` is a substring of `"21st Suffolk"`, so a substring match
    would silently merge two districts' rosters. `_normalize` folds the `&`/`and`
    and ordinal-word differences between how a user types a district and how the
    log writes it.

    The year comes from the end of the reporting period, which is days before
    the election the filing is about — so a window straddling New Year belongs to
    the year its election falls in.
    """
    target = _normalize(district.description)
    matched = []
    for row in reports.fetch_special_reports(stage):
        parsed = _parse_office_sought(row.office_sought)
        if parsed is None:
            # Not a House or Senate seat: the sweep also carries municipal,
            # mayoral and Governor's Council specials.
            continue
        office, description = parsed
        if office != district.office or _normalize(description) != target:
            continue
        if row.period is None or row.period.end.year != year:
            continue
        matched.append(row)
    return matched


def _span(periods: list[ReportingPeriod]) -> ReportingPeriod:
    """The envelope of `periods` — earliest start to latest end.

    Candidates in one special election routinely file different windows for it:
    across the whole log, 43 of 65 district-years hold more than one distinct
    pre-primary window, and every one of those resolves to a single election
    once overlapping windows are merged. A depository filer's window and a
    non-depository filer's simply start on different days. So differing windows
    are spanned, not treated as rival elections.
    """
    return ReportingPeriod(
        start=min(period.start for period in periods),
        end=max(period.end for period in periods),
    )


def _candidate_period(candidate: SpecialCandidate) -> ReportingPeriod | None:
    """The window a candidate's operative filing actually covers."""
    if candidate.report is None:
        return None
    start = candidate.report.get("startDateValue")
    end = candidate.report.get("endDateValue")
    if start is None or end is None:
        return None
    return ReportingPeriod(start=start, end=end)


def _select_stage(
    district: District,
    year: int,
    requested: SpecialStage | None,
) -> tuple[SpecialStage, list[SpecialReportRow]]:
    """Pick the stage to summarize, and return its rows.

    With no `--stage`, the general wins when both were held: a special's two
    stages are two filing windows of one contest, not two elections, and the
    general is the contest. The primary stays one flag away and is named on
    stderr so the narrower view is never invisible.
    """
    held = {
        stage: rows
        for stage in SpecialStage
        if (rows := _rows_for_district(district, year, stage))
    }

    if not held:
        raise SpecialRaceError(
            f"No special election found for {district.full_label} in {year}"
        )

    if requested is not None:
        if requested not in held:
            was = ", ".join(stage.value for stage in held)
            raise SpecialRaceError(
                f"No special {requested.value} found for {district.label} in "
                f"{year}; the special {was} was held that year"
            )
        return requested, held[requested]

    stage = SpecialStage.GENERAL if SpecialStage.GENERAL in held else SpecialStage.PRIMARY
    if stage is SpecialStage.GENERAL and SpecialStage.PRIMARY in held:
        primary_period = _span([row.period for row in held[SpecialStage.PRIMARY]])
        render.status(
            f"note: a special primary was also held ({primary_period.label}); "
            f"see it with --stage primary"
        )
    return stage, held[stage]


def build_special_roster(
    district: District,
    year: int,
    stage: SpecialStage,
    rows: list[SpecialReportRow],
) -> list[SpecialCandidate]:
    """Resolve each filer in `rows` to their operative filing for the stage.

    The sweep rows carry money, and it is unusable: the log returns every
    amendment generation, so a row's total identifies a version rather than a
    candidate. `fetch_reports` defaults to `OnlyCurrent=true` and returns the
    surviving version with the amended figures, which is what this reads.
    """
    by_cpf_id: dict[int, str] = {}
    for row in rows:
        by_cpf_id.setdefault(row.cpf_id, row.name)

    plural = "" if len(by_cpf_id) == 1 else "s"
    render.status(
        f"Reading filings for {len(by_cpf_id)} candidate{plural} in "
        f"{district.label}, {year}..."
    )
    roster = []
    for cpf_id, name in by_cpf_id.items():
        report = reports.find_stage_report(reports.fetch_reports(cpf_id), stage, year)
        roster.append(SpecialCandidate(cpf_id=cpf_id, name=name, report=report))
    return roster


def _special_sort_key(candidate: SpecialCandidate) -> Any:
    # Receipts descending, as the regular table orders. A candidate who filed
    # nothing sorts last rather than as a zero-raiser.
    return (candidate.receipts is None, -(candidate.receipts or 0), candidate.name)


def _render_special_table(
    district: District,
    stage: SpecialStage,
    period: ReportingPeriod,
    roster: list[SpecialCandidate],
) -> None:
    """Print the special-election header and table to stdout.

    The header names the filing period and no election date: OCPF publishes none
    for a special (`filingSchedules/2013` returns empty strings for both), and a
    date derived from the filing window would be a guess shown as a fact.
    """
    windows = {p for p in (_candidate_period(c) for c in roster) if p is not None}
    print(f"District:  {district.full_label}")
    print(f"Election:  special {stage.value}")
    if len(windows) > 1:
        print(f"Period:    {period.label} (candidates' filing windows differ)")
    else:
        print(f"Period:    {period.label}")
    print()

    table_rows = [
        [
            candidate.name,
            NOT_REPORTED if candidate.report is None
            else render.format_currency(candidate.receipts),
            NOT_REPORTED if candidate.report is None
            else render.format_currency(candidate.expenditures),
        ]
        for candidate in sorted(roster, key=_special_sort_key)
    ]
    headers = ["Candidate", "Raised in Period", "Spent in Period"]
    print(render.render_table(table_rows, headers, right_align=[1, 2]))
    print()
    print(
        "Figures are each candidate's operative filing for the period above, "
        "not year-to-date."
    )
    print("OCPF publishes no election date for a special election.")
    if any(candidate.report is None for candidate in roster):
        print(f"{NOT_REPORTED} = the candidate filed no report for this stage.")


def _period_json(period: ReportingPeriod | None) -> dict | None:
    if period is None:
        return None
    return {
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
        "label": period.label,
    }


def _special_json(
    district: District,
    stage: SpecialStage,
    period: ReportingPeriod,
    roster: list[SpecialCandidate],
) -> list[dict]:
    """One self-contained record per candidate, numbers as numbers."""
    return [
        {
            "cpfId": candidate.cpf_id,
            "name": candidate.name,
            "districtCode": district.code,
            "office": district.office,
            "districtDescription": district.description,
            "stage": stage.value,
            # The window this candidate's own filing covers, which is what
            # their figures are the total of. `span` is the whole race's.
            "reportingPeriod": _period_json(_candidate_period(candidate)),
            "reportingPeriodSpan": _period_json(period),
            "reportId": None if candidate.report is None else candidate.report.get("reportId"),
            "receipts": candidate.receipts,
            "expenditures": candidate.expenditures,
        }
        for candidate in sorted(roster, key=_special_sort_key)
    ]


def run_special(
    district: District,
    year: int,
    requested_stage: SpecialStage | None,
    json_output: bool,
) -> None:
    """The `--special` path: roster from the sweep, money from the filings."""
    stage, rows = _select_stage(district, year, requested_stage)
    roster = build_special_roster(district, year, stage, rows)

    # The period shown comes from the filings the figures came from, so the
    # header describes exactly the money in the table. Only when nobody filed
    # does it fall back to the windows the sweep advertised.
    windows = [p for p in (_candidate_period(c) for c in roster) if p is not None]
    period = _span(windows or [row.period for row in rows])

    if json_output:
        render.emit_json(_special_json(district, stage, period, roster))
    else:
        _render_special_table(district, stage, period, roster)


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
    special: bool = typer.Option(
        False,
        "--special",
        help="Summarize a special election held in the year, not the regular cycle",
    ),
    stage: SpecialStage = typer.Option(
        None,
        "--stage",
        help="Which stage of the special election (default: the general)",
    ),
) -> None:
    """Financial summary of the candidates in a legislative district.

    Year-to-date for the regular cycle; with `--special`, the filing-period
    totals for a special election held that year.
    """
    if year is None:
        # Avoid importing datetime at module load; current year is a runtime fact.
        from datetime import date

        year = date.today().year

    try:
        resolved = resolve_district(district, year)
    except DistrictResolutionError as exc:
        render.error(str(exc))
        for cand in exc.candidates:
            render.status(f"  {cand.full_label}")
        raise typer.Exit(code=1)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    if stage is not None and not special:
        render.error("--stage applies only to --special")
        raise typer.Exit(code=1)

    if special:
        # Branches before the legislative-feed fetch, so the regular path below
        # issues exactly the requests it issued before this option existed.
        try:
            run_special(resolved, year, stage, json_output)
        except SpecialRaceError as exc:
            render.error(str(exc))
            raise typer.Exit(code=1)
        except api.OcpfApiError as exc:
            render.error(str(exc))
            raise typer.Exit(code=1)
        return

    try:
        merged = fetch_merged_field(year)
        matched = filter_by_district(merged, resolved.code)
        historical = False
        # The current-cycle feeds only carry money from ~2020 on. For earlier
        # cycles they resolve names but leave the money blank, so fall back to
        # the district-scoped historical summaries (final full-cycle totals).
        if not has_money(matched) and resolved.code is not None:
            # `onballot/finsummaries` is addressed by code; a district known only
            # by name has nothing to ask it for.
            hist_rows = normalize_finsummaries(
                fetch_finsummaries(year, resolved.code)
            )
            if hist_rows:
                matched = hist_rows
                historical = True
        if not matched:
            render.error(
                f"No candidates found for {resolved.full_label} in {year}; if a "
                f"special election was held that year, reach it with --special"
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
