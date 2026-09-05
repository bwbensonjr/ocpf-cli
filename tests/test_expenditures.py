"""Tests for `ocpf expenditures`: filtering, rollup, exit codes, JSON."""

from __future__ import annotations

import json
from datetime import date

import pytest
from typer.testing import CliRunner

from ocpf_cli import api, resolve, search
from ocpf_cli.cli import app
from ocpf_cli.commands import expenditures

runner = CliRunner()


def _item(**kwargs):
    item = {
        "vendor": "Acme",
        "amount": "$100.00",
        "date": "6/1/2026",
        "purpose": "Printing",
        "recordTypeDescription": "Committee Reported Expenditure",
        "reportId": 1,
        "id": kwargs.pop("id", None) or 1,
    }
    item.update(kwargs)
    return search.annotate([item])[0]


FIXTURE = [
    _item(id=1, vendor="East Coast Printing", amount="$5,000.00", date="3/2/2026"),
    _item(id=2, vendor="Scale To Win", amount="$250.50", date="7/15/2026"),
    _item(id=3, vendor="Actblue", amount="$12.00", date="1/9/2025"),
    _item(
        id=4,
        vendor="OUTGOING WIRE TRANSFER",
        clarifiedName="Middle Seat",
        amount="$6,000.00",
        date="7/29/2026",
        recordTypeDescription="Bank Reported Expenditure",
    ),
]


def _install(monkeypatch, items, *, cpf_id=17436):
    monkeypatch.setattr(resolve, "fetch_merged_field", lambda year: [])
    monkeypatch.setattr(search, "fetch_expenditures", lambda c: list(items))
    monkeypatch.setattr(expenditures.search, "fetch_expenditures", lambda c: list(items))


# --- 3.1 filtering ---


def test_filter_by_year():
    got = expenditures.filter_items(FIXTURE, year=2026)
    assert {i["id"] for i in got} == {1, 2, 4}


def test_filter_by_since_and_until():
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, since=date(2026, 7, 1))} == {2, 4}
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, until=date(2026, 3, 2))} == {1, 3}


def test_filter_by_vendor_is_case_insensitive_substring():
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, vendor="printing")} == {1}
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, vendor="SCALE")} == {2}


def test_filter_by_vendor_matches_clarified_name_and_filed_string():
    # The wire transfer is findable under either the bank string or the payee
    # OCPF clarified it to.
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, vendor="wire")} == {4}
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, vendor="middle seat")} == {4}


def test_filter_by_amount_bounds():
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, min_amount=1000)} == {1, 4}
    assert {i["id"] for i in expenditures.filter_items(FIXTURE, max_amount=250.50)} == {2, 3}


def test_filters_combine_conjunctively():
    got = expenditures.filter_items(FIXTURE, year=2026, min_amount=1000, vendor="coast")
    assert {i["id"] for i in got} == {1}


def test_filter_matching_nothing_returns_empty():
    assert expenditures.filter_items(FIXTURE, vendor="Connection Strategies") == []


def test_parse_date_option_accepts_both_formats():
    assert expenditures.parse_date_option("2026-01-31", "--since") == date(2026, 1, 31)
    assert expenditures.parse_date_option("1/31/2026", "--since") == date(2026, 1, 31)
    assert expenditures.parse_date_option(None, "--since") is None
    with pytest.raises(ValueError):
        expenditures.parse_date_option("last tuesday", "--since")


# --- 3.2 rollup ---


def test_group_by_vendor_orders_by_total_descending():
    groups = expenditures.group_by_vendor(FIXTURE)
    assert [g["vendor"] for g in groups][:2] == ["Middle Seat", "East Coast Printing"]
    assert groups[0]["total"] == 6000.0


def test_grouped_totals_sum_to_itemized_total():
    groups = expenditures.group_by_vendor(FIXTURE)
    assert sum(g["total"] for g in groups) == pytest.approx(
        sum(i["amountValue"] for i in FIXTURE)
    )


def test_ocpf_clarified_variants_collapse_into_one_row():
    # OCPF resolved three bank-OCR spellings to one payee; a fourth record was
    # filed under that name directly. One recipient, four filed spellings.
    variants = [
        _item(id=1, vendor="JOVANA CALUILB", clarifiedName="Jovana Calvillo", amount="$5,250.00"),
        _item(id=2, vendor="JIVANA CALVILLE", clarifiedName="Jovana Calvillo", amount="$5,000.00"),
        _item(id=3, vendor="JOVANA CALVILLO", clarifiedName="Jovana Calvillo", amount="$5,000.00"),
        _item(id=4, vendor="Jovana Calvillo", amount="$5,000.00"),
    ]
    groups = expenditures.group_by_vendor(variants)

    assert len(groups) == 1
    assert groups[0]["vendor"] == "Jovana Calvillo"
    assert groups[0]["total"] == 20250.0
    assert groups[0]["count"] == 4
    assert groups[0]["clarified"] is True
    assert len(groups[0]["filedAs"]) == 4
    assert "JIVANA CALVILLE" in groups[0]["filedAs"]


def test_similar_unclarified_names_are_never_merged():
    # No clarification means no merge: asserting these are one person would be
    # our inference, not OCPF's.
    similar = [
        _item(id=1, vendor="Rivera Consulting Inc", amount="$2,500.00"),
        _item(id=2, vendor="Riversa Consulting Inc.", amount="$2,500.00"),
    ]
    groups = expenditures.group_by_vendor(similar)
    assert len(groups) == 2


def test_group_marks_bank_reported():
    groups = expenditures.group_by_vendor(FIXTURE)
    by_name = {g["vendor"]: g for g in groups}
    assert by_name["Middle Seat"]["bankReported"] is True
    assert by_name["Scale To Win"]["bankReported"] is False


# --- 4.x rendering and limit ---


def test_itemized_output_lists_records_and_total(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--year", "2026"])
    assert result.exit_code == 0
    assert "East Coast Printing" in result.stdout
    assert "$11,250.50" in result.stdout
    assert "(3 records)" in result.stdout


def test_clarified_payee_shows_filed_string_alongside(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--vendor", "wire"])
    assert result.exit_code == 0
    assert "Middle Seat (OUTGOING WIRE TRANSFER)" in result.stdout


def test_bank_reported_records_are_marked(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--vendor", "wire"])
    assert "bank" in result.stdout


def test_limit_caps_rows_but_not_the_total(monkeypatch):
    _install(monkeypatch, FIXTURE)
    full = runner.invoke(app, ["expenditures", "17436", "--year", "2026"])
    limited = runner.invoke(app, ["expenditures", "17436", "--year", "2026", "--limit", "1"])

    assert limited.exit_code == 0
    assert "Showing 1 of 3 records" in limited.stdout
    # The total describes every matching record, not only the displayed one.
    assert "$11,250.50" in limited.stdout and "$11,250.50" in full.stdout
    assert "(3 records)" in limited.stdout


def test_by_vendor_view(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--year", "2026", "--by-vendor"])
    assert result.exit_code == 0
    assert "Middle Seat" in result.stdout
    assert "3 vendors" in result.stdout


def test_by_vendor_total_matches_itemized_total(monkeypatch):
    _install(monkeypatch, FIXTURE)
    itemized = runner.invoke(app, ["expenditures", "17436", "--json"])
    grouped = runner.invoke(app, ["expenditures", "17436", "--by-vendor", "--json"])

    assert json.loads(itemized.stdout)["total"] == json.loads(grouped.stdout)["total"]


# --- 4.5 JSON ---


def test_json_emits_numeric_values_and_provenance(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--vendor", "wire", "--json"])
    payload = json.loads(result.stdout)

    record = payload["records"][0]
    assert record["amountValue"] == 6000.0
    assert record["amount"] == "$6,000.00"
    assert record["payee"] == "Middle Seat"
    assert record["vendor"] == "OUTGOING WIRE TRANSFER"
    assert record["isClarified"] is True
    assert record["isBankReported"] is True
    assert record["reportId"] == 1


def test_json_by_vendor_emits_groups_with_filed_spellings(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--by-vendor", "--json"])
    payload = json.loads(result.stdout)

    assert "vendors" in payload and "records" not in payload
    middle = [g for g in payload["vendors"] if g["vendor"] == "Middle Seat"][0]
    assert middle["filedAs"] == ["OUTGOING WIRE TRANSFER"]


# --- 5.x exit codes ---


def test_empty_filtered_result_exits_zero_and_reports_scope(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--vendor", "Connection Strategies"])

    assert result.exit_code == 0
    assert "No expenditures" in result.stdout
    assert "Connection Strategies" in result.stdout
    assert "searched 4 records" in result.stdout


def test_empty_filtered_result_json_exits_zero(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(
        app, ["expenditures", "17436", "--vendor", "Connection Strategies", "--json"]
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["records"] == []
    assert payload["total"] == 0.0
    assert payload["searchedRecords"] == 4


def test_filer_with_no_expenditure_records_exits_nonzero(monkeypatch):
    _install(monkeypatch, [])
    result = runner.invoke(app, ["expenditures", "17436"])
    assert result.exit_code == 1


def test_ambiguous_name_exits_nonzero(monkeypatch):
    field = [
        {"cpfId": 115, "filerName": "Smith, John", "officeSought": "House, 1st"},
        {"cpfId": 116, "filerName": "Smith, Jane", "officeSought": "House, 2nd"},
    ]
    monkeypatch.setattr(resolve, "fetch_merged_field", lambda year: field)
    result = runner.invoke(app, ["expenditures", "Smith"])
    assert result.exit_code == 1


def test_unknown_name_exits_nonzero(monkeypatch):
    monkeypatch.setattr(resolve, "fetch_merged_field", lambda year: [])
    result = runner.invoke(app, ["expenditures", "Nobody At All"])
    assert result.exit_code == 1


def test_api_error_exits_nonzero(monkeypatch):
    monkeypatch.setattr(resolve, "fetch_merged_field", lambda year: [])

    def boom(cpf_id):
        raise api.OcpfApiError("upstream exploded", path="search/items")

    monkeypatch.setattr(expenditures.search, "fetch_expenditures", boom)
    result = runner.invoke(app, ["expenditures", "17436"])
    assert result.exit_code == 1


def test_bad_date_option_exits_nonzero(monkeypatch):
    _install(monkeypatch, FIXTURE)
    result = runner.invoke(app, ["expenditures", "17436", "--since", "last tuesday"])
    assert result.exit_code == 1
