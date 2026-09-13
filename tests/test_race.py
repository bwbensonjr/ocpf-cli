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


# --- Special elections --------------------------------------------------------

import json

import pytest

from ocpf_cli import reports
from ocpf_cli.districts import District
from ocpf_cli.reports import SpecialStage


@pytest.fixture(autouse=True)
def _clear_sweep_cache():
    reports.fetch_special_reports.cache_clear()
    yield
    reports.fetch_special_reports.cache_clear()


def _log(cpf_id, name, office, period, report_id, type_id):
    return {
        "cpfId": cpf_id,
        "reportId": report_id,
        "reportTypeId": type_id,
        "fullNameReverse": name,
        "officeSought": office,
        "reportingPeriod": period,
        # Present in the live rows and deliberately unused: the log returns
        # every amendment generation, so these identify a version.
        "amendmentDisplay": "<br>Amendment",
        "receiptTotal": "$9,940.00",
        "expenditureTotal": "$6,329.57",
    }


def _filing(report_id, description, start, end, receipts, expenditures):
    return {
        "reportId": report_id,
        "reportTypeDescription": description,
        "startDate": start,
        "endDate": end,
        "receiptTotal": receipts,
        "expenditureTotal": expenditures,
    }


GENERAL = reports.SPECIAL_PRE_ELECTION_TYPE_ID
PRIMARY = reports.SPECIAL_PRE_PRIMARY_TYPE_ID


def _install_special(
    monkeypatch,
    log_rows,
    filings,
    *,
    districts=None,
    calls=None,
):
    """Serve a sweep and per-filer report lists through one fake get_json."""

    def fake(path, params=None, **kwargs):
        if calls is not None:
            calls.append(path)
        if path == "districts":
            return districts if districts is not None else _districts()
        if path == reports.REPORT_LOG_PATH:
            rows = [r for r in log_rows if r["reportTypeId"] == params["ReportTypeId"]]
            start = params["StartIndex"] - 1
            return rows[start : start + params["PageSize"]]
        if path.startswith("reports/baseReportTypes/"):
            return [{"baseReportTypeId": 8, "baseReportTypeDescription": "Other"}]
        if path.startswith("reports/reportList/"):
            cpf_id = int(path.rsplit("/", 1)[1])
            rows = filings.get(cpf_id, [])
            return {"summary": {"count": len(rows)}, "items": rows}
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(api, "get_json", fake)


def _bristol_log():
    return [
        _log(15658, "Steinhof, David", "House 6th Bristol", "7/27/13 - 8/23/13", 199084, GENERAL),
        # The superseded generations the live log also returns.
        _log(15658, "Steinhof, David", "House 6th Bristol", "7/27/13 - 8/23/13", 181035, GENERAL),
        _log(15658, "Steinhof, David", "House 6th Bristol", "7/27/13 - 8/23/13", 178138, GENERAL),
        _log(13597, "Fiola, Carole", "House 6th Bristol", "7/27/13 - 8/23/13", 180940, GENERAL),
        _log(15658, "Steinhof, David", "House 6th Bristol", "7/1/13 - 7/26/13", 199083, PRIMARY),
    ]


def _bristol_filings():
    return {
        # OnlyCurrent=true leaves exactly the operative version behind.
        15658: [
            _filing(199084, "Pre-election Report (Special) (ND)", "7/27/2013", "8/23/2013", "$13,530.00", "$6,829.57"),
            _filing(199083, "Pre-primary Report (Special) (ND)", "7/1/2013", "7/26/2013", "$2,790.00", "$1,918.83"),
        ],
        13597: [
            _filing(180940, "Pre-election Report (Special) (ND)", "7/27/2013", "8/23/2013", "$6,535.00", "$22,751.61"),
        ],
    }


def _bristol_districts():
    return [
        {"office": "House", "code": 214, "description": "6th Bristol"},
        {"office": "Senate", "code": 166, "description": "Suffolk and Middlesex"},
    ]


def test_special_roster_excludes_non_legislative_offices(monkeypatch):
    # The sweep also carries municipal, mayoral and Governor's Council specials.
    log_rows = _bristol_log() + [
        _log(90001, "Munro, Pat", "Municipal, Worcester", "7/27/13 - 8/23/13", 900001, GENERAL),
        _log(90002, "Cole, Sam", "Governor's Council 8th District", "7/27/13 - 8/23/13", 900002, GENERAL),
    ]
    _install_special(monkeypatch, log_rows, _bristol_filings(), districts=_bristol_districts())

    district = District(code=214, office="House", description="6th Bristol")
    rows = race._rows_for_district(district, 2013, SpecialStage.GENERAL)

    assert {row.cpf_id for row in rows} == {15658, 13597}


@pytest.mark.parametrize(
    "description",
    ["Worcester and Norfolk", "Worcester & Norfolk", "worcester  and   norfolk"],
)
def test_special_roster_matches_ampersand_and_spacing_forms(monkeypatch, description):
    log_rows = [
        _log(10315, "Moore, Michael", "Senate Worcester & Norfolk", "7/27/13 - 8/23/13", 1, GENERAL)
    ]
    _install_special(monkeypatch, log_rows, {})

    district = District(code=140, office="Senate", description=description)
    rows = race._rows_for_district(district, 2013, SpecialStage.GENERAL)

    assert [row.cpf_id for row in rows] == [10315]


def test_special_roster_matches_ordinal_word_forms(monkeypatch):
    log_rows = [
        _log(1, "A, B", "House 6th Bristol", "7/27/13 - 8/23/13", 1, GENERAL)
    ]
    _install_special(monkeypatch, log_rows, {})

    district = District(code=214, office="House", description="Sixth Bristol")
    rows = race._rows_for_district(district, 2013, SpecialStage.GENERAL)

    assert [row.cpf_id for row in rows] == [1]


def test_special_roster_does_not_substring_match_a_different_district(monkeypatch):
    # "1st Suffolk" is a substring of "21st Suffolk": a substring match here
    # would silently merge two districts' rosters.
    log_rows = [
        _log(1, "A, B", "House 21st Suffolk", "7/27/13 - 8/23/13", 1, GENERAL)
    ]
    _install_special(monkeypatch, log_rows, {})

    district = District(code=323, office="House", description="1st Suffolk")

    assert race._rows_for_district(district, 2013, SpecialStage.GENERAL) == []


def test_special_roster_excludes_the_other_chamber(monkeypatch):
    log_rows = [
        _log(1, "A, B", "Senate 6th Bristol", "7/27/13 - 8/23/13", 1, GENERAL)
    ]
    _install_special(monkeypatch, log_rows, {})

    district = District(code=214, office="House", description="6th Bristol")

    assert race._rows_for_district(district, 2013, SpecialStage.GENERAL) == []


def test_special_roster_narrows_to_the_requested_year(monkeypatch):
    log_rows = [
        _log(1, "A, B", "House 6th Bristol", "7/27/13 - 8/23/13", 1, GENERAL),
        _log(2, "C, D", "House 6th Bristol", "7/27/14 - 8/23/14", 2, GENERAL),
        # A window straddling New Year belongs to the year its election falls in.
        _log(3, "E, F", "House 6th Bristol", "12/20/12 - 1/15/13", 3, GENERAL),
    ]
    _install_special(monkeypatch, log_rows, {})

    district = District(code=214, office="House", description="6th Bristol")
    rows = race._rows_for_district(district, 2013, SpecialStage.GENERAL)

    assert {row.cpf_id for row in rows} == {1, 3}


def test_special_no_election_for_district_and_year_exits_nonzero(monkeypatch):
    _install_special(monkeypatch, _bristol_log(), _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "1999", "--special"])

    assert result.exit_code == 1
    assert "No special election found" in result.output
    assert "1999" in result.output


def test_special_defaults_to_the_general_and_names_the_primary(monkeypatch):
    _install_special(monkeypatch, _bristol_log(), _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special"])

    assert result.exit_code == 0, result.output
    assert "special general" in result.output
    assert "7/27/2013 - 8/23/2013" in result.output
    # The narrower view is named, never silently dropped.
    assert "--stage primary" in result.output
    assert "7/1/2013 - 7/26/2013" in result.output


def test_special_uses_the_only_stage_present(monkeypatch):
    primary_only = [r for r in _bristol_log() if r["reportTypeId"] == PRIMARY]
    _install_special(monkeypatch, primary_only, _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special"])

    assert result.exit_code == 0, result.output
    assert "special primary" in result.output
    assert "--stage" not in result.output


def test_special_requested_stage_not_held_names_the_stage_that_was(monkeypatch):
    primary_only = [r for r in _bristol_log() if r["reportTypeId"] == PRIMARY]
    _install_special(monkeypatch, primary_only, _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(
        app, ["race", "214", "--year", "2013", "--special", "--stage", "general"]
    )

    assert result.exit_code == 1
    assert "No special general found" in result.output
    assert "the special primary was held" in result.output


def test_special_stage_requires_special(monkeypatch):
    _install_special(monkeypatch, _bristol_log(), _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--stage", "general"])

    assert result.exit_code == 1
    assert "--stage applies only to --special" in result.output


def test_special_rejects_an_unknown_stage_before_any_request(monkeypatch):
    calls: list[str] = []
    _install_special(
        monkeypatch, _bristol_log(), _bristol_filings(),
        districts=_bristol_districts(), calls=calls,
    )

    result = runner.invoke(
        app, ["race", "214", "--year", "2013", "--special", "--stage", "bogus"]
    )

    assert result.exit_code != 0
    assert calls == []


def test_special_money_comes_from_the_operative_filing_not_the_sweep(monkeypatch):
    # Steinhof's four generations run $9,940.00 as filed to $13,530.00 amended,
    # and every generation is in the sweep. Reading the sweep's total would
    # understate him by 36%; `OnlyCurrent` leaves only the amended filing.
    _install_special(monkeypatch, _bristol_log(), _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special"])

    assert result.exit_code == 0, result.output
    assert "$13,530.00" in result.output
    assert "$9,940.00" not in result.output


def test_special_candidate_with_no_operative_filing_is_shown_as_not_reported(monkeypatch):
    filings = _bristol_filings()
    # Fiola is on the roster but filed nothing operative for the stage.
    del filings[13597]
    _install_special(monkeypatch, _bristol_log(), filings, districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special"])

    assert result.exit_code == 0, result.output
    # Shown, not dropped; and not as a zero, which would assert she raised none.
    assert "Fiola, Carole" in result.output
    assert race.NOT_REPORTED in result.output


def test_special_table_labels_money_as_period_not_ytd(monkeypatch):
    _install_special(monkeypatch, _bristol_log(), _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special"])

    assert "Raised in Period" in result.output
    assert "Spent in Period" in result.output
    assert "Raised YTD" not in result.output
    assert "Cash on Hand" not in result.output


def test_special_header_names_a_period_and_no_election_date(monkeypatch):
    calls: list[str] = []
    _install_special(
        monkeypatch, _bristol_log(), _bristol_filings(),
        districts=_bristol_districts(), calls=calls,
    )

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special"])

    assert "Period:    7/27/2013 - 8/23/2013" in result.output
    # OCPF publishes no special election date, so none is fetched or shown.
    assert not any(c.startswith("filingSchedules") for c in calls)
    assert "Election:  special general" in result.output


def test_special_spans_differing_filing_windows(monkeypatch):
    log_rows = [
        _log(1, "Forry, Linda Dorcena", "Senate 1st Suffolk", "4/13/13 - 5/10/13", 11, GENERAL),
        _log(2, "Ureneck, Joseph Anthony", "Senate 1st Suffolk", "4/23/13 - 5/20/13", 22, GENERAL),
    ]
    filings = {
        1: [_filing(11, "Pre-election Report (Special)", "4/13/2013", "5/10/2013", "$1.00", "$2.00")],
        2: [_filing(22, "Pre-election Report (Special) (ND)", "4/23/2013", "5/20/2013", "$3.00", "$4.00")],
    }
    districts = [{"office": "Senate", "code": 130, "description": "1st Suffolk"}]
    _install_special(monkeypatch, log_rows, filings, districts=districts)

    result = runner.invoke(app, ["race", "130", "--year", "2013", "--special"])

    assert result.exit_code == 0, result.output
    # One election, spanned — not two rival elections.
    assert "Period:    4/13/2013 - 5/20/2013" in result.output
    assert "windows differ" in result.output
    assert "Forry, Linda Dorcena" in result.output
    assert "Ureneck, Joseph Anthony" in result.output


def test_special_json_carries_ids_numbers_and_periods(monkeypatch):
    _install_special(monkeypatch, _bristol_log(), _bristol_filings(), districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    by_cpf_id = {row["cpfId"]: row for row in payload}

    assert by_cpf_id[15658]["reportId"] == 199084
    assert by_cpf_id[15658]["receipts"] == 13530.0
    assert by_cpf_id[15658]["expenditures"] == 6829.57
    assert by_cpf_id[13597]["reportId"] == 180940
    assert by_cpf_id[13597]["receipts"] == 6535.0
    assert by_cpf_id[15658]["stage"] == "general"
    assert by_cpf_id[15658]["reportingPeriod"]["label"] == "7/27/2013 - 8/23/2013"
    assert by_cpf_id[15658]["reportingPeriodSpan"]["start"] == "2013-07-27"


def test_special_json_marks_a_missing_filing_as_null(monkeypatch):
    filings = _bristol_filings()
    del filings[13597]
    _install_special(monkeypatch, _bristol_log(), filings, districts=_bristol_districts())

    result = runner.invoke(app, ["race", "214", "--year", "2013", "--special", "--json"])

    payload = {row["cpfId"]: row for row in json.loads(result.stdout)}
    # Null, never 0 — the distinction the table spells out as "not reported".
    assert payload[13597]["receipts"] is None
    assert payload[13597]["reportId"] is None


def test_race_without_special_names_the_flag_when_empty(monkeypatch):
    responses = {
        "districts": _districts(),
        race.DEPOSITORY_PATH.format(year=2013): {"reports": [], "summary": {}},
        race.NON_DEPOSITORY_PATH.format(year=2013): [],
        "onballot/finsummaries/2013/294": [],
    }
    monkeypatch.setattr(api, "get_json", _dispatch(responses))

    result = runner.invoke(app, ["race", "294", "--year", "2013"])

    assert result.exit_code == 1
    assert "--special" in result.output


def test_regular_path_issues_no_special_requests(monkeypatch):
    # Decision 7: --special branches before the feed fetch, so the regular path
    # runs the requests it ran before this option existed.
    calls: list[str] = []
    responses = {
        "districts": _districts(),
        race.DEPOSITORY_PATH.format(year=2026): {
            "reports": [
                {
                    "cpfId": 1,
                    "filerName": "Alpha",
                    "districtCodeSought": 166,
                    "districtCodeHeld": 166,
                    "receiptsYtdNumeric": 12345.0,
                    "bankReportEndDate": "6/30/2026",
                }
            ],
            "summary": {},
        },
        race.NON_DEPOSITORY_PATH.format(year=2026): [],
        "filingSchedules/2026": {"primaryElectionDate": "9/1/2026"},
    }
    monkeypatch.setattr(api, "get_json", _dispatch(responses, calls))

    result = runner.invoke(app, ["race", "166", "--year", "2026"])

    assert result.exit_code == 0, result.output
    assert calls == [
        "districts",
        race.DEPOSITORY_PATH.format(year=2026),
        race.NON_DEPOSITORY_PATH.format(year=2026),
        "filingSchedules/2026",
    ]
    assert reports.REPORT_LOG_PATH not in calls
