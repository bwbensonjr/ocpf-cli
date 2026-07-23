"""Output rendering helpers: aligned human tables and JSON emission.

Conventions (per clig.dev):
- Data goes to stdout. Human status/progress and errors go to stderr, so a
  `--json` stdout stays a clean, pipeable document.
- `emit_json` prints only JSON to stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Sequence


def status(message: str) -> None:
    """Print a human status/progress line to stderr (never stdout)."""
    print(message, file=sys.stderr)


def error(message: str) -> None:
    """Print an error line to stderr."""
    print(f"error: {message}", file=sys.stderr)


def emit_json(value: Any) -> None:
    """Print `value` as a JSON document to stdout and nothing else."""
    json.dump(value, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def format_currency(amount: float | int | None) -> str:
    """Format a numeric dollar amount as `$1,234.56`. None -> empty string."""
    if amount is None:
        return ""
    return f"${amount:,.2f}"


def render_table(
    rows: Sequence[Sequence[Any]],
    headers: Sequence[str],
    *,
    right_align: Sequence[int] | None = None,
) -> str:
    """Render `rows` as an aligned, labeled table.

    `right_align` is a set of column indexes to right-justify (e.g. currency).
    Returns the table as a string; the caller prints it to stdout.
    """
    right = set(right_align or ())
    str_rows = [["" if cell is None else str(cell) for cell in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: Sequence[str]) -> str:
        out = []
        for i, cell in enumerate(cells):
            if i in right:
                out.append(cell.rjust(widths[i]))
            else:
                out.append(cell.ljust(widths[i]))
        return "  ".join(out).rstrip()

    lines = [fmt_row(list(headers))]
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))).rstrip())
    for row in str_rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)
