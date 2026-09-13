"""Tests for the report endpoint client: fan-out, paging, coercion, not-found."""

from __future__ import annotations

from datetime import date

import pytest

from ocpf_cli import api, reports


def _report(n: int, **kwargs) -> dict:
    row = {
        "reportId": n,
        "reportTypeDescription": "Year-end Report (ND)",
        "reportingPeriod": "1/1/2013 - 12/31/2013",
        "startDate": "1/1/2013",
        "endDate": "12/31/2013",
        "reportYear": 2013,
        "dateFiledDisplay": "1/15/2014",
        "receiptTotal": "$100.00",
        "expenditureTotal": "$50.00",
        "startBalance": "$10.00",
        "endBalance": "$60.00",
    }
    row.update(kwargs)
    return row


def _install_list(
    monkeypatch,
    per_type: dict,
    *,
    types: list | None = None,
    calls: list | None = None,
    page_size: int | None = None,
):
    """Serve `per_type` ({baseReportTypeId: [rows]}) through a fake get_json."""
    size = page_size or reports.PAGE_SIZE
    base_types = types if types is not None else [
        {"baseReportTypeId": k, "baseReportTypeDescription": f"Type {k}"} for k in per_type
    ]

    def fake(path, params=None, **kwargs):
        if calls is not None:
            calls.append((path, params))
        if path.startswith("reports/baseReportTypes/"):
            return base_types
        if path.startswith("reports/reportList/"):
            rows = per_type.get(params["BaseReportTypeId"], [])
            if params["StartIndex"] < 1:
                # The live API returns HTTP 500 for StartIndex=0.
                raise api.OcpfApiError("boom", path=path, status_code=500)
            start = params["StartIndex"] - 1
            return {"summary": {"count": len(rows)}, "items": rows[start : start + size]}
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(api, "get_json", fake)


# --- 1.2 base report types ---


def test_base_report_types_returns_pairs(monkeypatch):
    _install_list(monkeypatch, {8: []})
    got = reports.fetch_base_report_types(14819)
    assert got == [{"baseReportTypeId": 8, "baseReportTypeDescription": "Type 8"}]


def test_base_report_types_empty_is_not_an_error(monkeypatch):
    # The real behavior of cpfId 96054: a filer with no reports.
    monkeypatch.setattr(api, "get_json", lambda path, params=None, **kw: [])
    assert reports.fetch_base_report_types(96054) == []


def test_base_report_types_rejects_unexpected_shape(monkeypatch):
    monkeypatch.setattr(api, "get_json", lambda path, params=None, **kw: {"oops": 1})
    with pytest.raises(api.OcpfApiError):
        reports.fetch_base_report_types(1)


# --- 1.3 paging ---


def test_single_page(monkeypatch):
    _install_list(monkeypatch, {8: [_report(i) for i in range(3)]})
    assert len(reports.fetch_report_list(14819, 8)) == 3


def test_three_pages_uses_one_based_offsets(monkeypatch):
    calls: list = []
    monkeypatch.setattr(reports, "PAGE_SIZE", 10)
    _install_list(
        monkeypatch,
        {8: [_report(i) for i in range(25)]},
        calls=calls,
        page_size=10,
    )

    rows = reports.fetch_report_list(14819, 8)

    assert len(rows) == 25
    offsets = [p["StartIndex"] for path, p in calls if path.startswith("reports/reportList/")]
    # 1-based record offsets: 1, 11, 21 — never 0, 10, 20.
    assert offsets == [1, 11, 21]
    assert 0 not in offsets
    assert [r["reportId"] for r in rows] == list(range(25))


def test_never_sends_start_index_zero(monkeypatch):
    calls: list = []
    _install_list(monkeypatch, {8: [_report(i) for i in range(3)]}, calls=calls)
    reports.fetch_report_list(14819, 8)
    assert all(p["StartIndex"] >= 1 for path, p in calls if "reportList" in path)


def test_only_current_is_sent_as_requested(monkeypatch):
    calls: list = []
    _install_list(monkeypatch, {8: [_report(1)]}, calls=calls)

    reports.fetch_report_list(14819, 8, only_current=True)
    reports.fetch_report_list(14819, 8, only_current=False)

    sent = [p["OnlyCurrent"] for path, p in calls if "reportList" in path]
    assert sent == ["true", "false"]


# --- 1.4 completeness ---


def test_short_read_raises(monkeypatch):
    def fake(path, params=None, **kwargs):
        if path.startswith("reports/baseReportTypes/"):
            return [{"baseReportTypeId": 8}]
        return {"summary": {"count": 10}, "items": [_report(1)]}

    monkeypatch.setattr(api, "get_json", fake)
    with pytest.raises(api.OcpfApiError, match="incomplete listing"):
        reports.fetch_report_list(14819, 8)


def test_stalled_page_raises(monkeypatch):
    def fake(path, params=None, **kwargs):
        return {"summary": {"count": 10}, "items": []}

    monkeypatch.setattr(api, "get_json", fake)
    with pytest.raises(api.OcpfApiError, match="incomplete listing"):
        reports.fetch_report_list(14819, 8)


# --- 1.5 fan-out and duplicate guard ---


def test_fan_out_merges_every_base_type(monkeypatch):
    _install_list(
        monkeypatch,
        {1: [_report(1), _report(2)], 8: [_report(3)]},
    )
    rows = reports.fetch_reports(14454)
    assert {r["reportId"] for r in rows} == {1, 2, 3}
    assert {r["baseReportTypeId"] for r in rows} == {1, 8}
    assert {r["baseReportTypeDescription"] for r in rows} == {"Type 1", "Type 8"}


def test_fan_out_passes_include_superseded(monkeypatch):
    calls: list = []
    _install_list(monkeypatch, {8: [_report(1)]}, calls=calls)
    reports.fetch_reports(14819, include_superseded=True)
    sent = [p["OnlyCurrent"] for path, p in calls if "reportList" in path]
    assert sent == ["false"]


def test_duplicate_report_id_raises(monkeypatch):
    # An overlapping page window is the silent failure mode of a 0-based
    # offset: plausible rows, inflated count. Fail rather than render it.
    def fake(path, params=None, **kwargs):
        if path.startswith("reports/baseReportTypes/"):
            return [{"baseReportTypeId": 1}, {"baseReportTypeId": 8}]
        return {"summary": {"count": 1}, "items": [_report(77)]}

    monkeypatch.setattr(api, "get_json", fake)
    with pytest.raises(api.OcpfApiError, match="more than once"):
        reports.fetch_reports(14454)


def test_filer_with_no_report_types_returns_empty(monkeypatch):
    _install_list(monkeypatch, {}, types=[])
    assert reports.fetch_reports(96054) == []


# --- 1.6 coercion ---


def test_annotate_parses_money_and_dates():
    row = reports.annotate([_report(1)])[0]
    assert row["receiptTotalValue"] == 100.0
    assert row["expenditureTotalValue"] == 50.0
    assert row["startBalanceValue"] == 10.0
    assert row["endBalanceValue"] == 60.0
    assert row["startDateValue"] == date(2013, 1, 1)
    assert row["endDateValue"] == date(2013, 12, 31)
    assert row["dateFiledValue"] == date(2014, 1, 15)


def test_annotate_handles_zero_and_malformed_values():
    row = reports.annotate(
        [
            _report(
                1,
                receiptTotal="$0.00",
                expenditureTotal="",
                startBalance="not money",
                startDate="",
                endDate=None,
                dateFiledDisplay="13/45/2020",
            )
        ]
    )[0]
    assert row["receiptTotalValue"] == 0.0
    assert row["expenditureTotalValue"] == 0.0
    assert row["startBalanceValue"] == 0.0
    assert row["startDateValue"] is None
    assert row["endDateValue"] is None
    assert row["dateFiledValue"] is None


# --- 1.7 single report and not-found ---


def test_fetch_report_returns_annotated_payload(monkeypatch):
    monkeypatch.setattr(
        api, "get_json", lambda path, params=None, **kw: _report(170378, receiptTotal="$3,512.97")
    )
    got = reports.fetch_report(170378)
    assert got["reportId"] == 170378
    assert got["receiptTotalValue"] == 3512.97


def test_low_report_id_raises_without_a_request(monkeypatch):
    def fake(path, params=None, **kwargs):
        raise AssertionError("should not have issued a request")

    monkeypatch.setattr(api, "get_json", fake)
    with pytest.raises(reports.ReportNotFoundError):
        reports.fetch_report(38)


def test_server_error_is_translated_to_not_found(monkeypatch):
    def fake(path, params=None, **kwargs):
        raise api.OcpfApiError("boom", path=path, status_code=500)

    monkeypatch.setattr(api, "get_json", fake)
    with pytest.raises(reports.ReportNotFoundError) as exc:
        reports.fetch_report(99999999)
    assert exc.value.report_id == 99999999
    # The message must not claim an outage it cannot know about.
    assert "returned no report" in str(exc.value)


def test_bad_request_is_translated_to_not_found(monkeypatch):
    def fake(path, params=None, **kwargs):
        raise api.OcpfApiError("boom", path=path, status_code=400)

    monkeypatch.setattr(api, "get_json", fake)
    with pytest.raises(reports.ReportNotFoundError):
        reports.fetch_report(12345)


def test_timeout_stays_an_api_error(monkeypatch):
    def fake(path, params=None, **kwargs):
        raise api.OcpfApiError("timed out", path=path)

    monkeypatch.setattr(api, "get_json", fake)
    with pytest.raises(api.OcpfApiError):
        reports.fetch_report(170378)


# --------------------------------------------------------------------------
# Cross-filer special-election sweep (`reports/log`)
# --------------------------------------------------------------------------


def _log_row(n: int, **kwargs) -> dict:
    row = {
        "cpfId": 15658,
        "reportId": n,
        "reportTypeId": reports.SPECIAL_PRE_ELECTION_TYPE_ID,
        "reportTypeDescription": "Pre-election Report (Special) (ND)",
        "reportingPeriod": "7/27/13 - 8/23/13",
        "fullNameReverse": "Steinhof, David",
        "officeSought": "House 6th Bristol",
        "amendmentDisplay": "<br>Amendment",
        "receiptTotal": "$9,940.00",
        "expenditureTotal": "$6,329.57",
    }
    row.update(kwargs)
    return row


def _install_log(monkeypatch, rows: list[dict], *, calls: list | None = None):
    """Serve `rows` through a fake get_json that pages like `reports/log`."""

    def fake(path, params=None, **kwargs):
        assert path == reports.REPORT_LOG_PATH
        if calls is not None:
            calls.append(dict(params or {}))
        start = params["StartIndex"]
        if start < 1:
            # The live log silently returns PageSize-1 rows for StartIndex=0,
            # which is how a 0-based pager corrupts a sweep without erroring.
            raise AssertionError("StartIndex must be 1-based")
        size = params["PageSize"]
        return rows[start - 1 : start - 1 + size]

    monkeypatch.setattr(api, "get_json", fake)


@pytest.fixture(autouse=True)
def _clear_sweep_cache():
    """The sweep memoizes for the process; tests must not share its result."""
    reports.fetch_special_reports.cache_clear()
    yield
    reports.fetch_special_reports.cache_clear()


@pytest.mark.parametrize(
    "value, expected",
    [
        # The shape every special-election row uses: a two-digit-year range.
        ("7/27/13 - 8/23/13", (date(2013, 7, 27), date(2013, 8, 23))),
        ("7/1/2019 - 12/31/2019", (date(2019, 7, 1), date(2019, 12, 31))),
        # No start year: it comes from the other end of the range.
        ("9/1 - 9/30/2026", (date(2026, 9, 1), date(2026, 9, 30))),
    ],
)
def test_parse_reporting_period_shapes(value, expected):
    period = reports.parse_reporting_period(value)
    assert (period.start, period.end) == expected


@pytest.mark.parametrize("value", ["1/13/26", "", "not a period", None, 7])
def test_parse_reporting_period_rejects_non_ranges(value):
    # A row whose window cannot be read cannot be placed in an election year,
    # so it yields None rather than a guess.
    assert reports.parse_reporting_period(value) is None


def test_reporting_period_label_uses_four_digit_years():
    period = reports.parse_reporting_period("7/27/13 - 8/23/13")
    assert period.label == "7/27/2013 - 8/23/2013"


def test_sweep_pages_from_a_one_based_start_index(monkeypatch):
    rows = [_log_row(n) for n in range(1, reports.PAGE_SIZE * 2 + 12)]
    calls: list[dict] = []
    _install_log(monkeypatch, rows, calls=calls)

    swept = reports.fetch_special_reports(reports.SpecialStage.GENERAL)

    assert len(swept) == len(rows)
    assert [c["StartIndex"] for c in calls] == [
        1,
        1 + reports.PAGE_SIZE,
        1 + 2 * reports.PAGE_SIZE,
    ]
    assert all(c["StartIndex"] != 0 for c in calls)
    # Every row is returned exactly once: overlapping offsets would duplicate.
    assert len({row.report_id for row in swept}) == len(rows)


def test_sweep_selects_the_stage_report_type(monkeypatch):
    calls: list[dict] = []
    _install_log(monkeypatch, [_log_row(1)], calls=calls)

    reports.fetch_special_reports(reports.SpecialStage.PRIMARY)

    assert calls[0]["ReportTypeId"] == reports.SPECIAL_PRE_PRIMARY_TYPE_ID


def test_sweep_is_memoized_for_the_process(monkeypatch):
    calls: list[dict] = []
    _install_log(monkeypatch, [_log_row(1)], calls=calls)

    first = reports.fetch_special_reports(reports.SpecialStage.GENERAL)
    second = reports.fetch_special_reports(reports.SpecialStage.GENERAL)

    assert first is second
    assert len(calls) == 1


def test_sweep_carries_no_display_strings(monkeypatch):
    # Decision 2: the log's money and its HTML amendment marker stop at the
    # sweep boundary. Money from a log row identifies an amendment generation,
    # not a candidate's total.
    _install_log(monkeypatch, [_log_row(1)])

    row = reports.fetch_special_reports(reports.SpecialStage.GENERAL)[0]

    assert not hasattr(row, "receipt_total")
    assert not hasattr(row, "amendment_display")
    assert "$" not in repr(row)
    assert "<br>" not in repr(row)
    assert row.period == reports.ReportingPeriod(date(2013, 7, 27), date(2013, 8, 23))


def test_sweep_drops_rows_without_a_cpf_id_or_office(monkeypatch):
    _install_log(
        monkeypatch,
        [
            _log_row(1),
            _log_row(2, cpfId=None),
            _log_row(3, officeSought=""),
        ],
    )

    swept = reports.fetch_special_reports(reports.SpecialStage.GENERAL)

    assert [row.report_id for row in swept] == [1]


def test_sweep_keeps_a_row_whose_period_is_unparseable(monkeypatch):
    _install_log(monkeypatch, [_log_row(1, reportingPeriod="1/13/26")])

    row = reports.fetch_special_reports(reports.SpecialStage.GENERAL)[0]

    assert row.period is None


def test_sweep_rejects_a_non_list_response(monkeypatch):
    monkeypatch.setattr(api, "get_json", lambda path, params=None, **kw: {"items": []})

    with pytest.raises(api.OcpfApiError, match="unexpected response shape"):
        reports.fetch_special_reports(reports.SpecialStage.GENERAL)


def test_find_stage_report_matches_both_filing_regimes():
    depository = _report(1, reportTypeDescription="Pre-Election Report (Special)")
    non_depository = _report(2, reportTypeDescription="Pre-election Report (Special) (ND)")

    for row in (depository, non_depository):
        found = reports.find_stage_report(
            reports.annotate([row]), reports.SpecialStage.GENERAL, 2013
        )
        assert found is row


def test_find_stage_report_ignores_other_stages_and_years():
    rows = reports.annotate(
        [
            _report(1, reportTypeDescription="Pre-primary Report (Special) (ND)"),
            _report(
                2,
                reportTypeDescription="Pre-election Report (Special) (ND)",
                startDate="7/27/2014",
                endDate="8/23/2014",
            ),
            _report(3, reportTypeDescription="Pre-election Report (ND)"),
        ]
    )

    assert reports.find_stage_report(rows, reports.SpecialStage.GENERAL, 2013) is None
    assert (
        reports.find_stage_report(rows, reports.SpecialStage.PRIMARY, 2013)["reportId"] == 1
    )
    assert (
        reports.find_stage_report(rows, reports.SpecialStage.GENERAL, 2014)["reportId"] == 2
    )


# --------------------------------------------------------------------------
# Per-filer log access and era-correct district naming
# --------------------------------------------------------------------------


def test_fetch_filer_log_pages_from_a_one_based_start_index(monkeypatch):
    rows = [_log_row(n) for n in range(1, reports.PAGE_SIZE + 12)]
    calls: list[dict] = []
    _install_log(monkeypatch, rows, calls=calls)

    fetched = reports.fetch_filer_log(11448)

    assert len(fetched) == len(rows)
    # Filtered by cpfId, and paged from 1 then 1+PAGE_SIZE -- never from 0,
    # where the live log silently returns PAGE_SIZE-1 rows.
    assert [c["CpfId"] for c in calls] == [11448, 11448]
    assert [c["StartIndex"] for c in calls] == [1, 1 + reports.PAGE_SIZE]
    # It stopped on the short page rather than requesting a third.
    assert len(calls) == 2


def test_offices_sought_in_year_separates_two_seats_by_period(monkeypatch):
    # The cpfId 11448 shape: one filer, two seats, distinguishable only by when
    # each filing was made. `filer/{cpfId}` would report just the later one.
    rows = [
        _log_row(1, reportingPeriod="1/1/14 - 6/30/14",
                 officeSought="Senate 1st Plymouth & Bristol"),
        _log_row(2, reportingPeriod="7/1/14 - 12/31/14",
                 officeSought="Senate 1st Plymouth & Bristol"),
        _log_row(3, reportingPeriod="1/1/22 - 6/30/22",
                 officeSought="Senate 3rd Bristol and Plymouth"),
    ]
    _install_log(monkeypatch, rows)

    assert reports.offices_sought_in_year(11448, 2014) == [
        "Senate 1st Plymouth & Bristol",
        "Senate 1st Plymouth & Bristol",
    ]
    assert reports.offices_sought_in_year(11448, 2022) == [
        "Senate 3rd Bristol and Plymouth"
    ]


def test_offices_sought_in_year_counts_a_straddling_period_by_its_end(monkeypatch):
    rows = [
        _log_row(1, reportingPeriod="11/1/13 - 1/31/14",
                 officeSought="Senate 1st Plymouth & Bristol"),
    ]
    _install_log(monkeypatch, rows)

    assert reports.offices_sought_in_year(11448, 2014) == [
        "Senate 1st Plymouth & Bristol"
    ]
    assert reports.offices_sought_in_year(11448, 2013) == []


def test_offices_sought_in_year_drops_rows_with_an_unreadable_period(monkeypatch):
    # A window that cannot be read cannot be placed in a year, so it is dropped
    # rather than guessed into one.
    rows = [
        _log_row(1, reportingPeriod="1/13/26",
                 officeSought="Senate 1st Plymouth & Bristol"),
        _log_row(2, reportingPeriod="", officeSought="Senate 1st Plymouth & Bristol"),
    ]
    _install_log(monkeypatch, rows)

    assert reports.offices_sought_in_year(11448, 2026) == []


def test_offices_sought_in_year_ignores_amendment_generations_money(monkeypatch):
    # The log returns every amendment generation; they differ in money but carry
    # the same office string. Reading the office is safe where reading the money
    # (which identifies a version, not a candidate) is not.
    rows = [
        _log_row(1, reportingPeriod="1/1/14 - 6/30/14",
                 officeSought="Senate 1st Plymouth & Bristol",
                 receiptTotal="$9,940.00"),
        _log_row(2, reportingPeriod="1/1/14 - 6/30/14",
                 officeSought="Senate 1st Plymouth & Bristol",
                 receiptTotal="$13,530.00", amendmentDisplay="<br>Amendment"),
    ]
    _install_log(monkeypatch, rows)

    offices = reports.offices_sought_in_year(11448, 2014)
    assert set(offices) == {"Senate 1st Plymouth & Bristol"}
