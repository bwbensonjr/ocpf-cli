"""Typer application: the `ocpf` command and its subcommands."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer

from .commands.filer import filer
from .commands.race import race

app = typer.Typer(
    name="ocpf",
    help="Query the Massachusetts OCPF campaign-finance API from the command line.",
    add_completion=False,
)


def _package_version() -> str:
    """Resolve the installed package version, or 'unknown' if unavailable.

    The version is dynamic (derived from the git tag at build time), so it lives
    in the installed package metadata rather than a source literal.
    """
    try:
        return version("ocpf")
    except PackageNotFoundError:
        return "unknown"


def _version_callback(value: bool) -> None:
    """Print `ocpf <version>` and exit when `--version` is passed."""
    if value:
        print(f"ocpf {_package_version()}")
        raise typer.Exit(code=0)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        help="Show the version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    """Query the OCPF campaign-finance API from the command line.

    With no subcommand, print top-level help and exit successfully. The
    callback also keeps the app in multi-command (group) mode so that `race`
    stays a named subcommand rather than collapsing into the root command.
    """
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit(code=0)


app.command("race")(race)
app.command("filer")(filer)


if __name__ == "__main__":
    app()
