"""Tests for rendering helpers."""

from __future__ import annotations

from ocpf_cli import render


def test_parse_currency():
    assert render.parse_currency("$63,727.50") == 63727.50
    assert render.parse_currency("$0.00") == 0.0
    assert render.parse_currency("") == 0.0
    assert render.parse_currency(None) == 0.0
    assert render.parse_currency("garbage") == 0.0
    # Already-numeric input passes through.
    assert render.parse_currency(1234.5) == 1234.5


def test_parse_currency_roundtrips_format_currency():
    assert render.parse_currency(render.format_currency(8896.49)) == 8896.49
