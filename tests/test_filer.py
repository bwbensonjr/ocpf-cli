"""Tests for filer resolution and payload fetch."""

from __future__ import annotations

import pytest

from ocpf_cli import api
from ocpf_cli.commands import filer


FIELD = [
    {"cpfId": 14454, "filerName": "Brownsberger, William N.", "officeSought": "Senate, Suffolk and Middlesex"},
    {"cpfId": 19588, "filerName": "Lander, Daniel", "officeSought": "Senate, Suffolk and Middlesex"},
    {"cpfId": 115, "filerName": "Smith, Middlesex Adams", "officeSought": "House, 1st Middlesex"},
    {"cpfId": 116, "filerName": "Smith, John", "officeSought": "House, 2nd Middlesex"},
]


def test_numeric_argument_used_as_cpfid_without_fetch(monkeypatch):
    # A numeric argument must NOT trigger a field fetch.
    def boom(_year):
        raise AssertionError("should not fetch the field for a numeric cpfId")

    monkeypatch.setattr(filer, "fetch_merged_field", boom)
    assert filer.resolve_filer("14454", 2026) == 14454


def test_unique_name_match(monkeypatch):
    monkeypatch.setattr(filer, "fetch_merged_field", lambda year: FIELD)
    assert filer.resolve_filer("brownsberger", 2026) == 14454


def test_name_match_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(filer, "fetch_merged_field", lambda year: FIELD)
    assert filer.resolve_filer("LANDER", 2026) == 19588


def test_ambiguous_name_lists_matches(monkeypatch):
    monkeypatch.setattr(filer, "fetch_merged_field", lambda year: FIELD)
    with pytest.raises(filer.FilerResolutionError) as exc:
        filer.resolve_filer("smith", 2026)
    ids = {m.cpf_id for m in exc.value.matches}
    assert ids == {115, 116}


def test_no_match_errors_with_cpfid_hint(monkeypatch):
    monkeypatch.setattr(filer, "fetch_merged_field", lambda year: FIELD)
    with pytest.raises(filer.FilerResolutionError) as exc:
        filer.resolve_filer("Nonexistent Person", 2026)
    assert exc.value.matches == []
    assert "cpfId" in str(exc.value)


def test_fetch_payload_success(monkeypatch):
    payload = {"filer": {"cpfId": 14454}, "ytdReport": {}, "logReports": []}
    monkeypatch.setattr(api, "get_json", lambda path, *a, **k: payload)
    assert filer.fetch_filer_payload(14454) is payload


def test_fetch_payload_http_400_maps_to_not_found(monkeypatch):
    def raise_400(path, *a, **k):
        raise api.OcpfApiError("bad", path=path, status_code=400)

    monkeypatch.setattr(api, "get_json", raise_400)
    with pytest.raises(filer.FilerResolutionError) as exc:
        filer.fetch_filer_payload(999999999)
    assert "No filer found" in str(exc.value)


def test_fetch_payload_other_http_error_reraises(monkeypatch):
    def raise_500(path, *a, **k):
        raise api.OcpfApiError("boom", path=path, status_code=500)

    monkeypatch.setattr(api, "get_json", raise_500)
    with pytest.raises(api.OcpfApiError):
        filer.fetch_filer_payload(14454)


def test_fetch_payload_empty_filer_is_not_found(monkeypatch):
    monkeypatch.setattr(api, "get_json", lambda path, *a, **k: {"filer": None})
    with pytest.raises(filer.FilerResolutionError):
        filer.fetch_filer_payload(123)


def test_office_str_handles_object_and_string():
    assert filer._office_str("Senate, X") == "Senate, X"
    assert filer._office_str({"officeDistrict": "Senate, Y"}) == "Senate, Y"
    assert filer._office_str(None) == ""
