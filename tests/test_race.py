"""Tests for the race command's merge, filter, and timeline helpers."""

from __future__ import annotations

from typer.testing import CliRunner

from ocpf_cli import api
from ocpf_cli.cli import app
from ocpf_cli.commands import race

runner = CliRunner()


def _dep_feed():
    return {
        "reports": [
            {
                "cpfId": 1,
                "filerName": "Alpha",
                "districtCodeSought": 166,
                "districtCodeHeld": 166,
                "receiptsYtdNumeric": 100.0,
                "bankReportEndDate": "6/30/2026",
            },
            {
                "cpfId": 2,
                "filerName": "Beta (depository)",
                "districtCodeSought": 166,
                "districtCodeHeld": -1,
                "receiptsYtdNumeric": 50.0,
                "bankReportEndDate": "3/31/2026",
            },
        ],
        "summary": {},
    }


def _nd_feed():
    # A bare list, as the non-depository feed returns. cpfId 2 collides with
    # the depository feed (depository must win); cpfId 3 is unique.
    return [
        {
            "cpfId": 2,
            "filerName": "Beta (non-depository, stale)",
            "districtCodeSought": 166,
            "districtCodeHeld": -1,
            "receiptsYtdNumeric": 999.0,
        },
        {
            "cpfId": 3,
            "filerName": "Gamma",
            "districtCodeSought": 999,
            "districtCodeHeld": -1,
            "receiptsYtdNumeric": 10.0,
        },
    ]


def test_reports_of_handles_dict_and_list():
    assert len(race._reports_of(_dep_feed())) == 2
    assert len(race._reports_of(_nd_feed())) == 2
    assert race._reports_of(None) == []


def test_merge_dedupes_by_cpfid_depository_wins(monkeypatch):
    responses = {
        race.DEPOSITORY_PATH.format(year=2026): _dep_feed(),
        race.NON_DEPOSITORY_PATH.format(year=2026): _nd_feed(),
    }
    monkeypatch.setattr(race.api, "get_json", lambda path, *a, **k: responses[path])

    merged = race.fetch_merged_field(2026)
    by_id = {r["cpfId"]: r for r in merged}

    # Three unique candidates, no duplicates.
    assert set(by_id) == {1, 2, 3}
    # Depository record wins the cpfId 2 conflict.
    assert by_id[2]["filerName"] == "Beta (depository)"


def test_filter_by_district_matches_sought_or_held():
    rows = race._reports_of(_dep_feed()) + _nd_feed()
    matched = race.filter_by_district(rows, 166)
    names = {r["filerName"] for r in matched}
    # Alpha (sought+held) and both Betas match 166; Gamma seeks 999.
    assert "Alpha" in names
    assert all("Gamma" != n for n in names)


def test_incumbent_detection():
    alpha = _dep_feed()["reports"][0]
    beta = _dep_feed()["reports"][1]
    assert race._is_incumbent(alpha, 166) is True
    assert race._is_incumbent(beta, 166) is False


def test_build_timeline_derives_as_of_and_flags_laggards(monkeypatch):
    monkeypatch.setattr(
        race.api,
        "get_json",
        lambda path, *a, **k: {
            "primaryElectionDate": "9/1/2026",
            "generalElectionDate": "11/3/2026",
        },
    )
    rows = race._reports_of(_dep_feed())  # Alpha 6/30, Beta 3/31
    timeline = race.build_timeline(2026, rows)

    assert timeline.primary_election_date == "9/1/2026"
    assert timeline.general_election_date == "11/3/2026"
    assert timeline.as_of_date == "6/30/2026"
    assert timeline.lagging_filers == ["Beta (depository)"]


def test_parse_report_date():
    assert race._parse_report_date("6/30/2026") == (2026, 6, 30)
    assert race._parse_report_date("") is None
    assert race._parse_report_date(None) is None
    assert race._parse_report_date("garbage") is None


# --- End-to-end source-selection tests (mocked API) ---------------------------


def _districts():
    return [
        {"office": "House", "code": 294, "description": "37th Middlesex"},
        {"office": "Senate", "code": 166, "description": "Suffolk and Middlesex"},
    ]


def _finsummaries_2008():
    return [
        {
            "cpfId": 14768,
            "filerName": "Benson, Jennifer",
            "districtCode": 0,
            "partyAffiliation": "Democratic",
            "isIncumbent": False,
            "isWinner": True,
            "receipts": "$63,727.50",
            "expenditures": "$54,831.01",
            "endBalance": "$8,896.49",
        },
        {
            "cpfId": 14818,
            "filerName": "Hayes, Kurt",
            "districtCode": 0,
            "partyAffiliation": "Republican",
            "isIncumbent": False,
            "isWinner": False,
            "receipts": "$26,402.00",
            "expenditures": "$24,652.76",
            "endBalance": "$1,749.24",
        },
    ]


def _dispatch(responses, calls=None):
    """Build a get_json stand-in that returns by path and records calls."""

    def fake(path, *a, **k):
        if calls is not None:
            calls.append(path)
        return responses.get(path, [])

    return fake


def test_race_falls_back_to_finsummaries_for_old_year(monkeypatch):
    calls: list[str] = []
    responses = {
        "districts": _districts(),
        # Current feeds resolve names but carry no money for 2008.
        race.DEPOSITORY_PATH.format(year=2008): {
            "reports": [
                {
                    "cpfId": 14768,
                    "filerName": "Benson, Jennifer",
                    "districtCodeSought": 294,
                    "districtCodeHeld": -1,
                }
            ],
            "summary": {},
        },
        race.NON_DEPOSITORY_PATH.format(year=2008): [],
        "onballot/finsummaries/2008/294": _finsummaries_2008(),
        "filingSchedules/2008": {
            "primaryElectionDate": "9/16/2008",
            "generalElectionDate": "11/4/2008",
        },
    }
    monkeypatch.setattr(api, "get_json", _dispatch(responses, calls))

    result = runner.invoke(app, ["race", "294", "--year", "2008"])

    assert result.exit_code == 0, result.output
    # Money from finsummaries is shown.
    assert "$63,727.50" in result.output
    assert "$26,402.00" in result.output
    # Historical mode: final-total labels, winner marker, no as-of line.
    assert "End Bal" in result.output
    assert "Won" in result.output
    assert "W won the general election" in result.output
    assert "As of" not in result.output
    # The fallback endpoint was actually consulted.
    assert "onballot/finsummaries/2008/294" in calls


def test_race_uses_current_feeds_and_skips_finsummaries(monkeypatch):
    calls: list[str] = []
    responses = {
        "districts": _districts(),
        race.DEPOSITORY_PATH.format(year=2026): {
            "reports": [
                {
                    "cpfId": 1,
                    "filerName": "Alpha",
                    "partyAffiliation": "Democratic",
                    "districtCodeSought": 166,
                    "districtCodeHeld": 166,
                    "receiptsYtdNumeric": 12345.0,
                    "expendituresYtdNumeric": 6000.0,
                    "currentCashOnHandNumeric": 6345.0,
                    "bankReportEndDate": "6/30/2026",
                }
            ],
            "summary": {},
        },
        race.NON_DEPOSITORY_PATH.format(year=2026): [],
        "filingSchedules/2026": {
            "primaryElectionDate": "9/1/2026",
            "generalElectionDate": "11/3/2026",
        },
    }
    monkeypatch.setattr(api, "get_json", _dispatch(responses, calls))

    result = runner.invoke(app, ["race", "166", "--year", "2026"])

    assert result.exit_code == 0, result.output
    assert "$12,345.00" in result.output
    # Current-cycle mode: YTD labels and as-of line, no winner column.
    assert "Raised YTD" in result.output
    assert "As of" in result.output
    assert "Won" not in result.output
    # finsummaries must not be called when the current feeds have money.
    assert not any(c.startswith("onballot/finsummaries") for c in calls)


def test_race_no_candidates_in_either_source_exits_nonzero(monkeypatch):
    responses = {
        "districts": _districts(),
        race.DEPOSITORY_PATH.format(year=2008): {"reports": [], "summary": {}},
        race.NON_DEPOSITORY_PATH.format(year=2008): [],
        "onballot/finsummaries/2008/294": [],
    }
    monkeypatch.setattr(api, "get_json", _dispatch(responses))

    result = runner.invoke(app, ["race", "294", "--year", "2008"])

    assert result.exit_code == 1
