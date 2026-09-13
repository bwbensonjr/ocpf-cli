"""Shared parsing for command-line option values.

Several commands accept the same kinds of option values — a date bound, most
of all — and each needs to reject a bad one with a message naming the flag the
user actually typed. That parsing lives here rather than in whichever command
module happened to need it first, so commands do not import from one another.
Same reason `resolve.py` exists.
"""

from __future__ import annotations

from datetime import date, datetime

# Accepted input spellings for a date option: ISO first, since that is what a
# script will produce, then OCPF's own display format, since that is what a
# user copying from the API or the web UI will have in hand.
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y")


def parse_date_option(value: str | None, flag: str) -> date | None:
    """Parse a date option as `YYYY-MM-DD` or OCPF's `M/D/YYYY`.

    Returns None for an absent value, so a caller can treat "not given" and
    "given as empty" alike. Raises `ValueError` naming `flag` otherwise, which
    the command turns into a message about the option the user typed.
    """
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{flag} expects a date like 2026-01-31 or 1/31/2026, got {value!r}")
