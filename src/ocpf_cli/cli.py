"""Typer application: the `ocpf` command and its subcommands."""

from __future__ import annotations

import typer

from .commands.filer import filer
from .commands.race import race

app = typer.Typer(
    name="ocpf",
    help="Query the Massachusetts OCPF campaign-finance API from the command line.",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
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
