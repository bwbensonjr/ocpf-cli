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
