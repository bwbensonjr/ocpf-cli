"""Smoke tests for CLI wiring: help, no-args, and unknown commands."""

from __future__ import annotations

from typer.testing import CliRunner

from ocpf_cli.cli import app

runner = CliRunner()


def test_no_args_shows_help_and_exits_zero():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in result.output
    assert "race" in result.output


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "race" in result.output


def test_race_is_a_named_subcommand():
    result = runner.invoke(app, ["race", "--help"])
    assert result.exit_code == 0
    assert "district" in result.output.lower()
    assert "--json" in result.output


def test_unknown_command_errors_nonzero():
    result = runner.invoke(app, ["bogus"])
    assert result.exit_code != 0
