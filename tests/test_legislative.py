"""Tests for the shared legislative field helpers, including the historical
`finsummaries` fallback source."""

from __future__ import annotations

from ocpf_cli import legislative


def _finsummaries_rows():
    # Shape returned by onballot/finsummaries/{year}/{code}: currency strings,
    # districtCode always 0, incumbency/winner as flags.
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


def test_has_money():
    assert legislative.has_money([{"receiptsYtdNumeric": 100.0}]) is True
    assert legislative.has_money([{"currentCashOnHandNumeric": 5.0}]) is True
    # Names present but no money -> False (the stale pre-2020 current-feed case).
    assert legislative.has_money([{"filerName": "X", "receiptsYtdNumeric": 0.0}]) is False
    assert legislative.has_money([]) is False


def test_normalize_finsummaries_maps_currency_and_flags():
    normalized = legislative.normalize_finsummaries(_finsummaries_rows())

    benson = normalized[0]
    assert benson["filerName"] == "Benson, Jennifer"
    assert benson["partyAffiliation"] == "Democratic"
    assert benson["receiptsYtdNumeric"] == 63727.50
    assert benson["expendituresYtdNumeric"] == 54831.01
    # endBalance maps to cash on hand.
    assert benson["currentCashOnHandNumeric"] == 8896.49
    assert benson["isWinner"] is True
    assert benson["isIncumbent"] is False

    # Normalized rows carry money, so has_money reports True.
    assert legislative.has_money(normalized) is True


def test_fetch_finsummaries_returns_list(monkeypatch):
    rows = _finsummaries_rows()
    monkeypatch.setattr(legislative.api, "get_json", lambda path, *a, **k: rows)
    fetched = legislative.fetch_finsummaries(2008, 294)
    assert len(fetched) == 2
    # A non-list payload degrades to an empty list.
    monkeypatch.setattr(legislative.api, "get_json", lambda path, *a, **k: {})
    assert legislative.fetch_finsummaries(2008, 294) == []
