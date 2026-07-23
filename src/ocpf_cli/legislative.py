"""Shared access to the legislative YTD field.

Both `ocpf race` and `ocpf filer` need the merged legislative field: `race`
filters it by district, `filer` matches names against it. The fetch/merge logic
lives here so there is one source of truth for the two feeds.
"""

from __future__ import annotations

from typing import Any

from . import api

# The two legislative feeds. The depository feed is the fuller record (bank
# reports) and wins on conflict; the non-depository feed catches smaller filers.
DEPOSITORY_PATH = "reports/legislative/depository/ytd/{year}"
NON_DEPOSITORY_PATH = "reports/legislative/race/nd/{year}"


def reports_of(payload: Any) -> list[dict]:
    """Normalize a feed payload to a list of report rows.

    The depository feed returns `{reports: [...], summary: {...}}`; the
    non-depository feed returns a bare list. Either way we want the rows.
    """
    if isinstance(payload, dict):
        return list(payload.get("reports", []))
    if isinstance(payload, list):
        return list(payload)
    return []


def fetch_merged_field(year: int) -> list[dict]:
    """Fetch both legislative feeds and merge by `cpfId` (depository wins)."""
    depository = reports_of(api.get_json(DEPOSITORY_PATH.format(year=year)))
    non_depository = reports_of(api.get_json(NON_DEPOSITORY_PATH.format(year=year)))

    merged: dict[Any, dict] = {}
    # Seed with non-depository first so depository rows overwrite on conflict.
    for row in non_depository:
        merged[row.get("cpfId")] = row
    for row in depository:
        merged[row.get("cpfId")] = row
    return list(merged.values())
