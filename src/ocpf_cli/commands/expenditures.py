"""`ocpf expenditures` — the payments a single filer has made.

Pipeline: resolve the argument to a `cpfId` (shared with `ocpf filer`) -> fetch
that filer's complete expenditure record set from `search/items` -> filter
locally -> render itemized or rolled up by payee (or JSON).

Filtering is deliberately local rather than pushed into the API. See
`search.py` for why: sibling filter parameters on that endpoint are silently
ignored rather than rejected, and an ignored filter looks exactly like one that
matched everything.
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from datetime import date, datetime
from typing import Any

import typer

from .. import api, render, search
from ..resolve import FilerResolutionError, resolve_filer

# `recordTypeDescription` values that mean the payee string came off a bank
# statement rather than a committee's own itemization. Such a payee can be an
# opaque bank description ("OUTGOING WIRE TRANSFER") rather than the true
# recipient, so the listing marks these rather than implying full disclosure.
BANK_REPORTED_MARKER = "bank reported"


def _payee(item: dict) -> str:
    """The effective payee: OCPF's clarified name when it supplied one, else as filed.

    `clarifiedName` is the disclosing authority's own resolution of a payee
    string, not an inference of ours. It is what turns three bank-OCR spellings
    of one consultant into one recipient, and what identifies the recipient
    behind an opaque bank description like "OUTGOING WIRE TRANSFER". Honoring it
    is more truthful than showing the raw string alone; `_filed_as` keeps the
    raw string visible so nothing is hidden by the substitution.
    """
    return (item.get("clarifiedName") or item.get("vendor") or "").strip()


def _filed_as(item: dict) -> str:
    """The payee string exactly as it appears in the filing."""
    return (item.get("vendor") or "").strip()


def _is_clarified(item: dict) -> bool:
    """True when OCPF supplied a clarified payee that differs from the filed one."""
    clarified = (item.get("clarifiedName") or "").strip()
    return bool(clarified) and clarified.casefold() != _filed_as(item).casefold()


def _payee_display(item: dict) -> str:
    """Payee for the itemized table: clarified name with the filed string shown."""
    if _is_clarified(item):
        return f"{_payee(item)} ({_filed_as(item)})"
    return _payee(item)


def _purpose(item: dict) -> str:
    """The purpose as filed, preferring OCPF's clarified purpose when present."""
    return (item.get("clarifiedPurpose") or item.get("purpose") or "").strip()


def _is_bank_reported(item: dict) -> bool:
    return BANK_REPORTED_MARKER in (item.get("recordTypeDescription") or "").lower()


def parse_date_option(value: str | None, flag: str) -> date | None:
    """Parse a `--since`/`--until` value as `YYYY-MM-DD` or OCPF's `M/D/YYYY`."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{flag} expects a date like 2026-01-31 or 1/31/2026, got {value!r}")


def filter_items(
    items: list[dict],
    *,
    year: int | None = None,
    since: date | None = None,
    until: date | None = None,
    vendor: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
) -> list[dict]:
    """Narrow `items` by the user's filters. Conditions combine conjunctively.

    `vendor` matches as a case-insensitive substring of the payee as filed,
    including the clarified name when OCPF supplied one.
    """
    needle = vendor.strip().lower() if vendor else None
    result = []

    for item in items:
        when = item.get("dateValue")
        amount = item.get("amountValue", 0.0)

        if year is not None and (when is None or when.year != year):
            continue
        if since is not None and (when is None or when < since):
            continue
        if until is not None and (when is None or when > until):
            continue
        if min_amount is not None and amount < min_amount:
            continue
        if max_amount is not None and amount > max_amount:
            continue
        if needle is not None:
            haystack = f"{item.get('vendor') or ''} {item.get('clarifiedName') or ''}".lower()
            if needle not in haystack:
                continue
        result.append(item)

    return result


def group_by_vendor(items: list[dict]) -> list[dict]:
    """Total `items` by payee, largest total first.

    Grouping is on the effective payee (see `_payee`): OCPF's clarified name
    where it supplied one, the filed string otherwise. This merges the bank-OCR
    spellings OCPF has itself resolved — "JOVANA CALUILB", "JIVANA CALVILLE" and
    "JOVANA CALVILLO" are one recipient by OCPF's own assertion, not by any
    guess of ours.

    What it will NOT do is infer a merge OCPF has not made. Two similar-looking
    unclarified strings stay two rows, because asserting an identity the data
    does not carry would be a fabrication in the one domain where who got paid
    is the entire question. Every filed spelling a group absorbed is kept in
    `filedAs` so the merge is always auditable.
    """
    groups: OrderedDict[str, dict] = OrderedDict()

    for item in items:
        payee = _payee(item)
        key = payee.casefold()
        group = groups.get(key)
        if group is None:
            group = {
                "vendor": payee,
                "total": 0.0,
                "count": 0,
                "bankReported": False,
                "clarified": False,
                "filedAs": [],
            }
            groups[key] = group
        group["total"] += item.get("amountValue", 0.0)
        group["count"] += 1
        if _is_bank_reported(item):
            group["bankReported"] = True
        if _is_clarified(item):
            group["clarified"] = True
        filed = _filed_as(item)
        if filed and filed not in group["filedAs"]:
            group["filedAs"].append(filed)

    for group in groups.values():
        group["filedAs"].sort(key=str.casefold)

    return sorted(groups.values(), key=lambda g: (-g["total"], g["vendor"].casefold()))


def _total(items: list[dict]) -> float:
    return sum(item.get("amountValue", 0.0) for item in items)


def _date_span(items: list[dict]) -> str:
    """Human description of the period `items` covers, for the no-match line."""
    dates = sorted(d for d in (i.get("dateValue") for i in items) if d is not None)
    if not dates:
        return "no dated records"
    if dates[0] == dates[-1]:
        return dates[0].strftime("%-m/%Y")
    return f"{dates[0].strftime('%-m/%Y')}-{dates[-1].strftime('%-m/%Y')}"


def _describe_filters(
    year: int | None,
    since: date | None,
    until: date | None,
    vendor: str | None,
    min_amount: float | None,
    max_amount: float | None,
) -> str:
    parts = []
    if vendor:
        parts.append(f'vendor "{vendor}"')
    if year is not None:
        parts.append(f"year {year}")
    if since is not None:
        parts.append(f"since {since.isoformat()}")
    if until is not None:
        parts.append(f"until {until.isoformat()}")
    if min_amount is not None:
        parts.append(f"min {render.format_currency(min_amount)}")
    if max_amount is not None:
        parts.append(f"max {render.format_currency(max_amount)}")
    return ", ".join(parts)


def _print_legend(*, any_bank: bool, any_clarified: bool) -> None:
    """Explain the markers, so neither a clarification nor a bank payee is silent."""
    # The legend goes to stderr (it is commentary, not data), so flush the table
    # first or the unbuffered stderr lines land above it in a terminal.
    sys.stdout.flush()
    if any_clarified:
        render.status(
            "Vendor shows OCPF's clarified payee, with the string as filed in "
            "parentheses."
        )
    if any_bank:
        render.status(
            '"bank" marks bank-reported records: the payee may be a bank '
            "description rather than the true recipient."
        )


def _render_itemized(items: list[dict], limit: int | None) -> None:
    shown = items[:limit] if limit is not None else items
    rows = [
        [
            item.get("date", ""),
            render.format_currency(item.get("amountValue")),
            _payee_display(item),
            _purpose(item),
            "bank" if _is_bank_reported(item) else "",
        ]
        for item in shown
    ]
    headers = ["Date", "Amount", "Vendor", "Purpose", "Src"]
    print(render.render_table(rows, headers, right_align=[1]))
    print()
    if limit is not None and len(items) > limit:
        print(f"Showing {len(shown)} of {len(items)} records (--limit {limit}).")
    print(f"Total: {render.format_currency(_total(items))}  ({len(items)} records)")
    _print_legend(
        any_bank=any(_is_bank_reported(i) for i in shown),
        any_clarified=any(_is_clarified(i) for i in shown),
    )


def _vendor_cell(group: dict) -> str:
    """Group label, noting how many filed spellings it absorbed when more than one."""
    spellings = len(group["filedAs"])
    if spellings > 1:
        return f"{group['vendor']} ({spellings} filed spellings)"
    return group["vendor"]


def _render_by_vendor(groups: list[dict], items: list[dict], limit: int | None) -> None:
    shown = groups[:limit] if limit is not None else groups
    rows = [
        [
            _vendor_cell(group),
            render.format_currency(group["total"]),
            group["count"],
            "bank" if group["bankReported"] else "",
        ]
        for group in shown
    ]
    headers = ["Vendor", "Total", "Count", "Src"]
    print(render.render_table(rows, headers, right_align=[1, 2]))
    print()
    if limit is not None and len(groups) > limit:
        print(f"Showing {len(shown)} of {len(groups)} vendors (--limit {limit}).")
    print(
        f"Total: {render.format_currency(_total(items))}  "
        f"({len(items)} records, {len(groups)} vendors)"
    )
    _print_legend(
        any_bank=any(g["bankReported"] for g in shown),
        any_clarified=any(g["clarified"] for g in shown),
    )


def _json_record(item: dict) -> dict[str, Any]:
    """One expenditure as JSON: numeric value alongside the filed display string."""
    when = item.get("dateValue")
    return {
        "date": item.get("date"),
        "dateValue": when.isoformat() if when else None,
        "amount": item.get("amount"),
        "amountValue": item.get("amountValue"),
        # `payee` is the effective recipient (clarified where OCPF clarified it);
        # `vendor` is always the string as filed, so both are recoverable.
        "payee": _payee(item),
        "vendor": item.get("vendor"),
        "clarifiedName": item.get("clarifiedName") or None,
        "isClarified": _is_clarified(item),
        "purpose": item.get("purpose"),
        "clarifiedPurpose": item.get("clarifiedPurpose") or None,
        "recordTypeDescription": item.get("recordTypeDescription"),
        "isBankReported": _is_bank_reported(item),
        "reportId": item.get("reportId"),
        "sourceDescription": item.get("sourceDescription"),
        "sourceLink": item.get("sourceLink"),
        "filerCpfId": item.get("filerCpfId"),
    }


def expenditures(
    filer: str = typer.Argument(
        ..., help="Numeric cpfId, or a candidate name (legislative filers)"
    ),
    year: int = typer.Option(None, "--year", help="Only expenditures dated in this year"),
    since: str = typer.Option(None, "--since", help="Only on/after this date (YYYY-MM-DD)"),
    until: str = typer.Option(None, "--until", help="Only on/before this date (YYYY-MM-DD)"),
    vendor: str = typer.Option(
        None, "--vendor", help="Only payees containing this text (case-insensitive)"
    ),
    min_amount: float = typer.Option(None, "--min-amount", help="Only amounts >= this"),
    max_amount: float = typer.Option(None, "--max-amount", help="Only amounts <= this"),
    by_vendor: bool = typer.Option(
        False, "--by-vendor", help="Group totals by payee instead of listing records"
    ),
    limit: int = typer.Option(None, "--limit", help="Cap the rows displayed"),
    resolve_year: int = typer.Option(
        None, "--resolve-year", help="Year used to resolve a candidate name (default: current)"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit the matching expenditures as JSON"
    ),
) -> None:
    """List and total the payments a single filer has made."""
    try:
        since_date = parse_date_option(since, "--since")
        until_date = parse_date_option(until, "--until")
    except ValueError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    # A name is matched against the legislative field for a year. That year is
    # about *resolution*, not about which expenditures to show, so it is a
    # separate flag from --year, which filters records.
    name_year = resolve_year or year or date.today().year

    try:
        cpf_id = resolve_filer(filer, name_year)
    except FilerResolutionError as exc:
        render.error(str(exc))
        for match in exc.matches:
            render.status(f"  {match.cpf_id}  {match.name}  ({match.office})")
        raise typer.Exit(code=1)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    try:
        items = search.fetch_expenditures(cpf_id)
    except api.OcpfApiError as exc:
        render.error(str(exc))
        raise typer.Exit(code=1)

    # No expenditure records at all is a dead end, not a finding: exit non-zero.
    if not items:
        render.error(f"No expenditure records on file for cpfId {cpf_id}")
        raise typer.Exit(code=1)

    matched = filter_items(
        items,
        year=year,
        since=since_date,
        until=until_date,
        vendor=vendor,
        min_amount=min_amount,
        max_amount=max_amount,
    )

    # A filter matching nothing is an answer ("they paid them nothing"), not a
    # failure: report it on stdout and exit zero.
    if not matched:
        described = _describe_filters(year, since_date, until_date, vendor, min_amount, max_amount)
        if json_output:
            render.emit_json(
                {
                    "filerCpfId": cpf_id,
                    "filters": described,
                    "searchedRecords": len(items),
                    "searchedSpan": _date_span(items),
                    "total": 0.0,
                    "records": [],
                }
            )
        else:
            suffix = f" matching {described}" if described else ""
            print(f"No expenditures{suffix}")
            print(f"(searched {len(items):,} records, {_date_span(items)})")
        return

    if json_output:
        if by_vendor:
            render.emit_json(
                {
                    "filerCpfId": cpf_id,
                    "total": _total(matched),
                    "recordCount": len(matched),
                    "vendors": group_by_vendor(matched),
                }
            )
        else:
            render.emit_json(
                {
                    "filerCpfId": cpf_id,
                    "total": _total(matched),
                    "recordCount": len(matched),
                    "records": [_json_record(item) for item in matched],
                }
            )
        return

    if by_vendor:
        _render_by_vendor(group_by_vendor(matched), matched, limit)
    else:
        _render_itemized(
            sorted(matched, key=lambda i: (i.get("dateValue") or date.min), reverse=True),
            limit,
        )
