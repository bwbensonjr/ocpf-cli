"""Tests for `ocpf reports` and `ocpf report`: filters, exit codes, JSON, near-misses."""

from __future__ import annotations

import json
from datetime import date

import pytest
from typer.testing import CliRunner

from ocpf_cli import api, reports as reports_api
from ocpf_cli.cli import app
from ocpf_cli.commands import reports as cmd

runner = CliRunner()


def _row(report_id, type_desc, start, end, year, filed, **kwargs):
    row = {
        "reportId": report_id,
        "reportTypeDescription": type_desc,
        "reportingPeriod": f"{start} - {end}",
        "startDate": start,
        "endDate": end,
        "reportYear": year,
        "dateFiledDisplay": filed,
        "receiptTotal": "$100.00",
        "expenditureTotal": "$50.00",
        "startBalance": "$0.00",
        "endBalance": "$50.00",
        "ocpfUsReportLink": f"https://www.ocpf.us/Reports/DisplayReport?id={report_id}",
    }
    row.update(kwargs)
    return row


FIXTURE = reports_api.annotate(
    [
        # Both spellings of the same report type: non-depository and depository.
        _row(170378, "Pre-election Report (Special) (ND)", "2/16/2013", "3/15/2013", 2013,
             "5/8/2013", isAmendment=True, previousReportId=170376),
        _row(742896, "Pre-Election Report (Special)", "9/1/2021", "9/30/2021", 2021, "10/5/2021"),
        _row(566246, "Pre-election Report (ND)", "8/23/2014", "10/17/2014", 2014, "3/9/2016"),
        _row(728208, "Year-end Report", "7/1/2019", "12/31/2019", 2019, "1/22/2020",
             isAmended=True, nextReportId=728209),
    ]
)


def _install(monkeypatch, rows=FIXTURE, *, cpf_id=14819, calls=None):
    monkeypatch.setattr(cmd, "resolve_filer", lambda q, y: cpf_id)

    def fake(cid, *, include_superseded=False):
        if calls is not None:
            calls.append(include_superseded)
        return list(rows)

    monkeypatch.setattr(reports_api, "fetch_reports", fake)


# --- 2.5 type filtering ---


def test_type_filter_matches_both_regime_spellings():
    # "Pre-election Report (Special) (ND)" and "Pre-Election Report (Special)"
    # are the same report type under the two filing regimes. A user asking for
    # pre-election reports wants both.
    got = cmd.filter_reports(FIXTURE, report_type="pre-election")
    assert {r["reportId"] for r in got} == {170378, 742896, 566246}


def test_type_filter_is_case_insensitive_substring():
    assert {r["reportId"] for r in cmd.filter_reports(FIXTURE, report_type="SPECIAL")} == {
        170378,
        742896,
    }
    assert {r["reportId"] for r in cmd.filter_reports(FIXTURE, report_type="year-end")} == {728208}


# --- 2.6 date and year filtering ---


def test_year_filter():
    assert {r["reportId"] for r in cmd.filter_reports(FIXTURE, year=2013)} == {170378}


def test_since_is_inclusive_at_the_period_end():
    # The 2013 filing covers 2/16 - 3/15. A --since of exactly its end date
    # must keep it; one day later must drop it.
    assert 170378 in {r["reportId"] for r in cmd.filter_reports(FIXTURE, since=date(2013, 3, 15))}
    assert 170378 not in {r["reportId"] for r in cmd.filter_reports(FIXTURE, since=date(2013, 3, 16))}


def test_until_is_inclusive_at_the_period_start():
    assert 170378 in {r["reportId"] for r in cmd.filter_reports(FIXTURE, until=date(2013, 2, 16))}
    assert 170378 not in {r["reportId"] for r in cmd.filter_reports(FIXTURE, until=date(2013, 2, 15))}


def test_date_bounds_match_a_period_that_spans_the_date():
    # The question a date bound answers is "which filing covers this date".
    got = cmd.filter_reports(FIXTURE, since=date(2013, 3, 1), until=date(2013, 3, 1))
    assert {r["reportId"] for r in got} == {170378}


def test_filters_combine_conjunctively():
    got = cmd.filter_reports(FIXTURE, report_type="pre-election", year=2014)
    assert {r["reportId"] for r in got} == {566246}


# --- 2.2/2.3 listing ---


def test_listing_shows_report_ids_and_periods(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "14819"])
    assert result.exit_code == 0
    assert "170378" in result.stdout
    assert "Pre-election Report (Special) (ND)" in result.stdout
    assert "2/16/2013 - 3/15/2013" in result.stdout
    assert "4 reports" in result.stdout


def test_listing_is_most_recent_first(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "14819"])
    ids = [line.split()[0] for line in result.stdout.splitlines() if line[:6].isdigit()]
    # Filing dates, newest first: 10/5/2021, 1/22/2020, 3/9/2016, 5/8/2013.
    assert ids == ["742896", "728208", "566246", "170378"]


def test_listing_covers_every_year_not_just_the_resolution_year(monkeypatch):
    # Resolving a name against one year's legislative field must not bound the
    # reports listed, or a 2013 special-election filing becomes unreachable.
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "Matewsky", "--resolve-year", "2026"])
    assert "170378" in result.stdout
    assert "728208" in result.stdout


def test_limit_reports_that_it_limited(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "14819", "--limit", "2"])
    assert "Showing 2 of 4 reports" in result.stdout
    assert "4 reports" in result.stdout


# --- 2.4 amendments ---


def test_amendment_rows_are_marked(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "14819"])
    lines = {line.split()[0]: line for line in result.stdout.splitlines() if line[:6].isdigit()}
    assert lines["170378"].endswith("amend")
    assert lines["728208"].endswith("amended")
    assert lines["566246"].rstrip()[-1].isdigit()


def test_include_superseded_is_passed_through(monkeypatch):
    calls: list = []
    _install(monkeypatch, calls=calls)
    runner.invoke(app, ["reports", "14819"])
    runner.invoke(app, ["reports", "14819", "--include-superseded"])
    assert calls == [False, True]


# --- 2.7 exit codes ---


def test_filter_matching_nothing_exits_zero(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "14819", "--type", "nonexistent"])
    assert result.exit_code == 0
    assert "No reports matching" in result.stdout
    assert 'type "nonexistent"' in result.stdout


def test_filer_with_no_reports_exits_non_zero(monkeypatch):
    _install(monkeypatch, rows=[])
    result = runner.invoke(app, ["reports", "14819"])
    assert result.exit_code == 1


def test_api_error_exits_non_zero(monkeypatch):
    monkeypatch.setattr(cmd, "resolve_filer", lambda q, y: 14819)

    def boom(cid, *, include_superseded=False):
        raise api.OcpfApiError("network down", path="reports/reportList/14819")

    monkeypatch.setattr(reports_api, "fetch_reports", boom)
    result = runner.invoke(app, ["reports", "14819"])
    assert result.exit_code == 1


# --- 2.8 JSON ---


def test_json_listing(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "14819", "--json"])
    payload = json.loads(result.stdout)
    assert payload["reportCount"] == 4
    assert payload["filerCpfId"] == 14819
    row = next(r for r in payload["reports"] if r["reportId"] == 170378)
    assert row["receiptTotalValue"] == 100.0
    assert row["isAmendment"] is True
    assert row["previousReportId"] == 170376
    assert row["reportLink"].endswith("id=170378")
    assert "Report" not in result.stdout.splitlines()[0]


def test_json_empty_result_is_valid_and_exits_zero(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["reports", "14819", "--type", "nope", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["reportCount"] == 0
    assert payload["reports"] == []


# --- 3.x the report detail command ---


DETAIL = reports_api.annotate(
    [
        dict(
            _row(170378, "Pre-election Report (Special) (ND)", "2/16/2013", "3/15/2013", 2013,
                 "5/8/2013", isAmendment=True, previousReportId=170376),
            committeeName="Matewsky Committee",
            candidateFullNameReverse="Matewsky, Wayne",
            officeDistrictSought="House, 28th Middlesex",
            treasurerFirstName="Gerard",
            treasurerLastName="Osterofsky",
            bankName="East Boston Savings",
            startBalance="$7,953.94",
            endBalance="$1,430.30",
            receiptItemizedTotal="$3,512.97",
            expenditureTotal="$10,036.61",
            receipts=[
                {"date": "3/10/2013", "amount": "$100.00", "fullNameReverse": "Antonuccio, Anthony",
                 "recordTypeDescription": "Individual", "description": ""}
            ],
            expenditures=[
                {"date": "3/2/2013", "amount": "$184.00", "fullNameReverse": "U.S. Post Office",
                 "recordTypeDescription": "General Expenditure", "description": "Stamps"}
            ],
            oopExpenditures=[],
        )
    ]
)[0]


def _install_detail(monkeypatch, payload=DETAIL):
    monkeypatch.setattr(reports_api, "fetch_report", lambda rid: payload)


def test_report_header_and_totals(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378"])
    assert result.exit_code == 0
    assert "Pre-election Report (Special) (ND)" in result.stdout
    assert "2/16/2013 - 3/15/2013" in result.stdout
    assert "Matewsky Committee" in result.stdout
    assert "House, 28th Middlesex" in result.stdout
    assert "$7,953.94" in result.stdout
    assert "$1,430.30" in result.stdout


def test_report_omits_line_items_by_default(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378"])
    assert "Antonuccio" not in result.stdout
    assert "U.S. Post Office" not in result.stdout


def test_report_prints_a_requested_schedule(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378", "--schedule", "expenditures"])
    assert "U.S. Post Office" in result.stdout
    assert "Stamps" in result.stdout
    assert "1 items" in result.stdout


def test_report_prints_each_requested_schedule_as_its_own_section(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(
        app, ["report", "170378", "--schedule", "receipts", "--schedule", "expenditures"]
    )
    assert "RECEIPTS" in result.stdout
    assert "EXPENDITURES" in result.stdout
    assert "Antonuccio" in result.stdout
    assert "U.S. Post Office" in result.stdout


def test_empty_schedule_is_reported_and_exits_zero(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378", "--schedule", "out-of-pocket"])
    assert result.exit_code == 0
    assert "no out-of-pocket recorded" in result.stdout


def test_unknown_schedule_names_the_valid_set(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378", "--schedule", "bogus"])
    assert result.exit_code == 1
    assert "unknown schedule" in result.output
    assert "out-of-pocket" in result.output


def test_amendment_lineage_is_shown(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378"])
    assert "amends report 170376" in result.stdout


def test_unamended_report_prints_no_marker(monkeypatch):
    plain = dict(DETAIL)
    plain["isAmendment"] = False
    plain["isAmended"] = False
    _install_detail(monkeypatch, plain)
    result = runner.invoke(app, ["report", "170378"])
    assert "Amendment" not in result.stdout


def test_report_link_is_printed(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378"])
    assert "DisplayReport?id=170378" in result.stdout


def test_not_found_exits_non_zero(monkeypatch):
    def missing(rid):
        raise reports_api.ReportNotFoundError(
            f"no report {rid}: the OCPF API returned no report for that id", report_id=rid
        )

    monkeypatch.setattr(reports_api, "fetch_report", missing)
    result = runner.invoke(app, ["report", "99999999"])
    assert result.exit_code == 1
    assert "no report 99999999" in result.output


def test_genuine_api_error_is_reported_as_one(monkeypatch):
    def boom(rid):
        raise api.OcpfApiError("Request to report/170378 timed out", path="report/170378")

    monkeypatch.setattr(reports_api, "fetch_report", boom)
    result = runner.invoke(app, ["report", "170378"])
    assert result.exit_code == 1
    assert "timed out" in result.output


def test_report_json_includes_requested_schedules(monkeypatch):
    _install_detail(monkeypatch)
    result = runner.invoke(app, ["report", "170378", "--json", "--schedule", "receipts"])
    payload = json.loads(result.stdout)
    assert payload["reportId"] == 170378
    assert payload["committeeName"] == "Matewsky Committee"
    assert len(payload["schedules"]["receipts"]) == 1
    assert payload["totals"]["Start balance"] == "$7,953.94"


# --- 4. near-miss handling between the singular and plural commands ---


def test_report_with_a_name_points_at_the_plural_command(monkeypatch):
    result = runner.invoke(app, ["report", "Matewsky"])
    assert result.exit_code == 1
    assert "is not a report id" in result.output
    assert "ocpf reports Matewsky" in result.output


def test_reports_with_a_report_id_points_at_the_singular_command(monkeypatch):
    _install(monkeypatch, rows=[], cpf_id=170378)
    result = runner.invoke(app, ["reports", "170378"])
    assert result.exit_code == 1
    assert "ocpf report 170378" in result.output
