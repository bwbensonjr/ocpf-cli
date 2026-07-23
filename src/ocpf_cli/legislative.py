"""Shared access to the legislative YTD field.

Both `ocpf race` and `ocpf filer` need the merged legislative field: `race`
filters it by district, `filer` matches names against it. The fetch/merge logic
lives here so there is one source of truth for the two feeds.
"""

from __future__ import annotations

from typing import Any

from . import api, render

# The two legislative feeds. The depository feed is the fuller record (bank
# reports) and wins on conflict; the non-depository feed catches smaller filers.
DEPOSITORY_PATH = "reports/legislative/depository/ytd/{year}"
NON_DEPOSITORY_PATH = "reports/legislative/race/nd/{year}"

# Historical fallback. The current-cycle feeds above are only populated from
# ~2020 on; earlier cycles live in this district-scoped endpoint, which returns
# a bare list of final full-cycle totals (not a YTD snapshot).
FINSUMMARIES_PATH = "onballot/finsummaries/{year}/{code}"


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


# The numeric money fields shared by the current-cycle feed rows and the
# normalized historical rows. Used to decide whether a field actually has money.
MONEY_FIELDS = (
    "receiptsYtdNumeric",
    "expendituresYtdNumeric",
    "currentCashOnHandNumeric",
)


def has_money(rows: list[dict]) -> bool:
    """True if any row carries a nonzero value in any money field.

    Drives the historical fallback: the current-cycle feeds resolve names for
    older cycles but leave the money blank, so "did we actually get money?" is
    the signal to fall back to `finsummaries`.
    """
    return any(row.get(field) for row in rows for field in MONEY_FIELDS)


def fetch_finsummaries(year: int, code: int) -> list[dict]:
    """Fetch the district-scoped historical financial summaries (a bare list)."""
    payload = api.get_json(FINSUMMARIES_PATH.format(year=year, code=code))
    return list(payload) if isinstance(payload, list) else []


def normalize_finsummaries(rows: list[dict]) -> list[dict]:
    """Map `finsummaries` rows into the shared candidate-row shape.

    The historical feed reports money as currency strings (`receipts`,
    `expenditures`, `endBalance`) and carries `isIncumbent`/`isWinner` flags.
    We parse the strings into the same numeric fields the current-cycle path
    uses so rendering, sorting, and `--json` work unchanged. `districtCode` is
    `0` on every row, so incumbency comes from the flag, not the code.
    """
    normalized = []
    for row in rows:
        normalized.append(
            {
                "cpfId": row.get("cpfId"),
                "filerName": row.get("filerName", ""),
                "partyAffiliation": row.get("partyAffiliation", ""),
                "receiptsYtdNumeric": render.parse_currency(row.get("receipts")),
                "expendituresYtdNumeric": render.parse_currency(
                    row.get("expenditures")
                ),
                "currentCashOnHandNumeric": render.parse_currency(
                    row.get("endBalance")
                ),
                "isIncumbent": bool(row.get("isIncumbent")),
                "isWinner": bool(row.get("isWinner")),
            }
        )
    return normalized
