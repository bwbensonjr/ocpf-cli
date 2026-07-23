"""Tests for the race command's merge, filter, and timeline helpers."""

from __future__ import annotations

from ocpf_cli.commands import race


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
