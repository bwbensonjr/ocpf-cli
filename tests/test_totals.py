"""Tests for `ocpf totals`: required window, category safety, exit codes, JSON."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from typer.testing import CliRunner

from ocpf_cli import api, search
from ocpf_cli.cli import app
from ocpf_cli.commands import totals as cmd

runner = CliRunner()

# Typer renders its own errors through rich, and rich styles the option name
# when it detects a CI terminal — under GitHub Actions `--end` comes back as
# `--` and `end` separated by escape codes, so a raw substring check passes
# locally and fails in CI. Assert against the plain text instead.
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(result) -> str:
    """`result.output` with terminal styling removed."""
    return ANSI.sub("", result.output)


def _install(monkeypatch, *, count=1277, total=401190.59, calls=None, cpf_id=14902):
    monkeypatch.setattr(cmd, "resolve_filer", lambda q, y: cpf_id)

    def fake(cid, category, start, end):
        if calls is not None:
            calls.append((cid, category, start, end))
        return count, total

    monkeypatch.setattr(search, "fetch_category_total", fake)


def _no_request(monkeypatch):
    """Fail loudly if anything reaches the network."""
    monkeypatch.setattr(cmd, "resolve_filer", lambda q, y: 14902)

    def boom(*args, **kwargs):
        raise AssertionError("should not have issued a request")

    monkeypatch.setattr(search, "fetch_category_total", boom)


# --- 3.4 reporting a total ---


def test_reports_count_total_and_window(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(app, ["totals", "14902", "--start", "2024-01-01", "--end", "2024-10-31"])
    assert result.exit_code == 0
    assert "1,277" in result.stdout
    assert "$401,190.59" in result.stdout
    # The window must never be separated from the figure.
    assert "2024-01-01 to 2024-10-31" in result.stdout


def test_window_may_cross_a_year_boundary(monkeypatch):
    calls: list = []
    _install(monkeypatch, count=1760, total=581434.45, calls=calls)
    result = runner.invoke(app, ["totals", "14902", "--start", "2023-11-01", "--end", "2024-10-25"])
    assert result.exit_code == 0
    assert calls[0][2] == date(2023, 11, 1)
    assert calls[0][3] == date(2024, 10, 25)
    assert "$581,434.45" in result.stdout


def test_ocpf_date_format_is_accepted(monkeypatch):
    calls: list = []
    _install(monkeypatch, calls=calls)
    result = runner.invoke(app, ["totals", "14902", "--start", "1/1/2024", "--end", "10/31/2024"])
    assert result.exit_code == 0
    assert calls[0][2] == date(2024, 1, 1)


# --- 3.6 empty window ---


def test_empty_window_is_a_finding_not_a_failure(monkeypatch):
    _install(monkeypatch, count=0, total=0.0)
    result = runner.invoke(app, ["totals", "14902", "--start", "2005-01-01", "--end", "2005-12-31"])
    assert result.exit_code == 0
    assert "$0.00" in result.stdout
    assert "2005-01-01 to 2005-12-31" in result.stdout


# --- 3.3 bounds are required and validated ---


def test_missing_end_bound_exits_non_zero(monkeypatch):
    _no_request(monkeypatch)
    result = runner.invoke(app, ["totals", "14902", "--start", "2024-01-01"])
    assert result.exit_code != 0
    assert "--end" in plain(result)


def test_missing_both_bounds_exits_non_zero(monkeypatch):
    _no_request(monkeypatch)
    result = runner.invoke(app, ["totals", "14902"])
    assert result.exit_code != 0


def test_unparseable_date_exits_non_zero_without_a_request(monkeypatch):
    _no_request(monkeypatch)
    result = runner.invoke(app, ["totals", "14902", "--start", "notadate", "--end", "2024-10-31"])
    assert result.exit_code == 1
    assert "--start" in plain(result)


def test_inverted_window_is_rejected_without_a_request(monkeypatch):
    _no_request(monkeypatch)
    result = runner.invoke(app, ["totals", "14902", "--start", "2024-12-31", "--end", "2024-01-01"])
    assert result.exit_code == 1
    assert "inverted" in plain(result)


# --- category safety ---


def test_receipts_is_the_default_category(monkeypatch):
    calls: list = []
    _install(monkeypatch, calls=calls)
    runner.invoke(app, ["totals", "14902", "--start", "2024-01-01", "--end", "2024-10-31"])
    assert calls[0][1] == search.CATEGORY_RECEIPTS


def test_expenditures_category_is_mapped_to_its_constant(monkeypatch):
    calls: list = []
    _install(monkeypatch, count=845, total=397182.30, calls=calls)
    result = runner.invoke(
        app,
        ["totals", "14902", "--start", "2023-11-01", "--end", "2024-10-25",
         "--category", "expenditures"],
    )
    assert calls[0][1] == search.CATEGORY_EXPENDITURES
    assert "expenditures" in result.stdout
    assert "$397,182.30" in result.stdout


def test_unknown_category_is_rejected_before_any_request(monkeypatch):
    _no_request(monkeypatch)
    result = runner.invoke(
        app,
        ["totals", "14902", "--start", "2024-01-01", "--end", "2024-10-31",
         "--category", "bogus"],
    )
    assert result.exit_code != 0
    assert "receipts" in plain(result)


def test_the_user_string_never_reaches_the_api_parameter():
    # The category the API sees comes from a fixed map, not from input.
    assert set(cmd.CATEGORY_CODES.values()) == {
        search.CATEGORY_RECEIPTS,
        search.CATEGORY_EXPENDITURES,
    }


# --- errors from the fetch layer ---


def test_api_error_exits_non_zero(monkeypatch):
    monkeypatch.setattr(cmd, "resolve_filer", lambda q, y: 14902)

    def boom(cid, category, start, end):
        raise api.OcpfApiError("the date filter was not applied", path="search/items")

    monkeypatch.setattr(search, "fetch_category_total", boom)
    result = runner.invoke(app, ["totals", "14902", "--start", "2024-01-01", "--end", "2024-10-31"])
    assert result.exit_code == 1
    assert "date filter was not applied" in plain(result)


def test_unresolvable_filer_exits_non_zero(monkeypatch):
    from ocpf_cli.resolve import FilerResolutionError

    def boom(q, y):
        raise FilerResolutionError("no match")

    monkeypatch.setattr(cmd, "resolve_filer", boom)
    result = runner.invoke(app, ["totals", "Nobody", "--start", "2024-01-01", "--end", "2024-10-31"])
    assert result.exit_code == 1


# --- 3.7 JSON ---


def test_json_output(monkeypatch):
    _install(monkeypatch)
    result = runner.invoke(
        app, ["totals", "14902", "--start", "2024-01-01", "--end", "2024-10-31", "--json"]
    )
    payload = json.loads(result.stdout)
    assert payload == {
        "filerCpfId": 14902,
        "category": "receipts",
        "start": "2024-01-01",
        "end": "2024-10-31",
        "recordCount": 1277,
        "total": 401190.59,
        "totalDisplay": "$401,190.59",
    }


def test_json_carries_both_bounds(monkeypatch):
    _install(monkeypatch, count=0, total=0.0)
    result = runner.invoke(
        app, ["totals", "14902", "--start", "2005-01-01", "--end", "2005-12-31", "--json"]
    )
    payload = json.loads(result.stdout)
    assert payload["start"] == "2005-01-01"
    assert payload["end"] == "2005-12-31"
    assert "cpfId" not in result.stdout
