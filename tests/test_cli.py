"""Smoke tests for CLI wiring: help, no-args, and unknown commands."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from ocpf_cli.cli import app

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    """Strip ANSI color codes so substring checks are color-independent.

    Rich colorizes Typer's help when a terminal (or CI's FORCE_COLOR) enables
    color, inserting escape codes that split option tokens like `--json`. The
    tests care that the option is listed, not whether it is styled.
    """
    return _ANSI.sub("", text)


def test_no_args_shows_help_and_exits_zero():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in _plain(result.output)
    assert "race" in _plain(result.output)


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "race" in _plain(result.output)


def test_race_is_a_named_subcommand():
    result = runner.invoke(app, ["race", "--help"])
    assert result.exit_code == 0
    assert "district" in _plain(result.output).lower()
    assert "--json" in _plain(result.output)


def test_both_commands_listed_in_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "race" in _plain(result.output)
    assert "filer" in _plain(result.output)


def test_filer_is_a_named_subcommand():
    result = runner.invoke(app, ["filer", "--help"])
    assert result.exit_code == 0
    assert "--json" in _plain(result.output)


def test_unknown_command_errors_nonzero():
    result = runner.invoke(app, ["bogus"])
    assert result.exit_code != 0


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    out = _plain(result.output)
    assert out.startswith("ocpf ")
    # A non-empty version token follows the program name.
    assert out.split("ocpf ", 1)[1].strip()


def test_version_short_flag():
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert _plain(result.output).startswith("ocpf ")


def test_version_short_circuits_subcommand(monkeypatch):
    # --version is a top-level option, so it precedes the subcommand name. If it
    # did not short-circuit, race would call the API; make any API call fail
    # loudly so the test proves the command never ran.
    import ocpf_cli.api as api

    def _boom(*a, **k):
        raise AssertionError("API should not be called when --version is passed")

    monkeypatch.setattr(api, "get_json", _boom)

    result = runner.invoke(app, ["--version", "race"])
    assert result.exit_code == 0
    assert _plain(result.output).startswith("ocpf ")
