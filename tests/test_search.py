"""Tests for the `search/items` client: paging, completeness, shape guards."""

from __future__ import annotations

from datetime import date

import pytest

from ocpf_cli import api, search


def _expenditure(n: int) -> dict:
    return {"vendor": f"Vendor {n}", "amount": "$1.00", "date": "1/2/2026"}


def _pager(total: int, monkeypatch, *, page_size: int | None = None, calls: list | None = None):
    """Install a fake get_json serving `total` records in pages."""
    size = page_size or search.PAGE_SIZE
    records = [_expenditure(i) for i in range(total)]

    def fake(path, params=None, **kwargs):
        if calls is not None:
            calls.append(params)
        # StartIndex is 1-based in the real API, and 0 behaves like 1.
        start = max(params["StartIndex"], 1) - 1
        return {"summary": {"count": total}, "items": records[start : start + size]}

    monkeypatch.setattr(api, "get_json", fake)
    return records


# --- 2.2 paging ---


def test_single_page(monkeypatch):
    _pager(3, monkeypatch)
    assert len(search.fetch_items({"CpfId": 1})) == 3


def test_three_pages_returns_all_records_and_makes_expected_calls(monkeypatch):
    calls: list = []
    monkeypatch.setattr(search, "PAGE_SIZE", 10)
    _pager(25, monkeypatch, page_size=10, calls=calls)

    items = search.fetch_items({"CpfId": 1})

    assert len(items) == 25
    # 1-based offsets: 1, 11, 21 — not 0, 10, 20.
    assert [c["StartIndex"] for c in calls] == [1, 11, 21]
    assert all(c["withSummary"] == "true" for c in calls)
    assert [i["vendor"] for i in items] == [f"Vendor {n}" for n in range(25)]


def test_page_boundary_does_not_duplicate_a_record(monkeypatch):
    # Regression: StartIndex is 1-based, so paging from a 0-based offset
    # re-fetches the boundary record and inflates the total. Caught against
    # live data as a 1,020th record duplicating the 1,000th.
    monkeypatch.setattr(search, "PAGE_SIZE", 10)
    _pager(20, monkeypatch, page_size=10)

    items = search.fetch_items({"CpfId": 1})

    assert len(items) == 20
    assert len({i["vendor"] for i in items}) == 20


def test_overlapping_pages_raise_rather_than_inflate(monkeypatch):
    # A pager that ignores StartIndex entirely: every page repeats page one.
    monkeypatch.setattr(search, "PAGE_SIZE", 10)
    monkeypatch.setattr(
        api,
        "get_json",
        lambda path, params=None, **k: {
            "summary": {"count": 15},
            "items": [_expenditure(i) for i in range(10)],
        },
    )

    with pytest.raises(api.OcpfApiError) as exc:
        search.fetch_items({"CpfId": 1})
    assert "inflated total" in str(exc.value)


def test_query_params_are_preserved_across_pages(monkeypatch):
    calls: list = []
    monkeypatch.setattr(search, "PAGE_SIZE", 10)
    _pager(15, monkeypatch, page_size=10, calls=calls)

    search.fetch_items({"CpfId": 17436, "SearchTypeCategory": "B"})

    assert all(c["CpfId"] == 17436 and c["SearchTypeCategory"] == "B" for c in calls)


# --- 2.3 completeness ---


def test_short_result_raises_rather_than_returning_partial(monkeypatch):
    # The API claims 100 records but only ever serves 2.
    def fake(path, params=None, **kwargs):
        first_page = params["StartIndex"] <= 1
        return {
            "summary": {"count": 100},
            "items": [_expenditure(0), _expenditure(1)] if first_page else [],
        }

    monkeypatch.setattr(api, "get_json", fake)

    with pytest.raises(api.OcpfApiError) as exc:
        search.fetch_items({"CpfId": 1})
    assert "2 records" in str(exc.value) and "100" in str(exc.value)


def test_stalled_pager_hits_the_page_ceiling(monkeypatch):
    # Every page comes back full, so the short-page exit never fires and the
    # accumulated count never reaches the reported one: only MAX_PAGES stops it.
    monkeypatch.setattr(search, "PAGE_SIZE", 2)
    monkeypatch.setattr(search, "MAX_PAGES", 5)
    monkeypatch.setattr(
        api,
        "get_json",
        lambda path, params=None, **k: {
            "summary": {"count": 10_000},
            "items": [_expenditure(0), _expenditure(1)],
        },
    )

    with pytest.raises(api.OcpfApiError) as exc:
        search.fetch_items({"CpfId": 1})
    assert "did not finish paging" in str(exc.value)


def test_short_page_ends_paging_even_when_count_disagrees(monkeypatch):
    # A short page means the API has no more to give; a count it cannot satisfy
    # is then a completeness failure, not a reason to keep asking.
    monkeypatch.setattr(search, "PAGE_SIZE", 10)
    monkeypatch.setattr(
        api,
        "get_json",
        lambda path, params=None, **k: {"summary": {"count": 100}, "items": [_expenditure(0)]},
    )

    with pytest.raises(api.OcpfApiError) as exc:
        search.fetch_items({"CpfId": 1})
    assert "refusing to report an incomplete total" in str(exc.value)


def test_missing_summary_returns_what_was_fetched(monkeypatch):
    # Without a count there is nothing to check against; one page is all we get.
    monkeypatch.setattr(
        api, "get_json", lambda path, params=None, **k: {"items": [_expenditure(0)]}
    )
    assert len(search.fetch_items({"CpfId": 1})) == 1


def test_non_dict_response_raises(monkeypatch):
    monkeypatch.setattr(api, "get_json", lambda path, params=None, **k: [1, 2, 3])
    with pytest.raises(api.OcpfApiError):
        search.fetch_items({"CpfId": 1})


# --- 2.4 receipts must never render as expenditures ---


def test_receipt_shaped_records_raise(monkeypatch):
    receipt = {
        "contributorCpfId": 80769,
        "fullNameReverse": "1199 SEIU MA PAC",
        "amount": "$500.00",
        "date": "8/3/2024",
    }
    monkeypatch.setattr(
        api, "get_json", lambda path, params=None, **k: {"summary": {"count": 1}, "items": [receipt]}
    )

    with pytest.raises(api.OcpfApiError) as exc:
        search.fetch_expenditures(17436)
    assert "money received as money spent" in str(exc.value)


def test_expenditure_query_uses_the_category_constant(monkeypatch):
    seen: dict = {}

    def fake(path, params=None, **kwargs):
        seen.update(params)
        return {"summary": {"count": 1}, "items": [_expenditure(0)]}

    monkeypatch.setattr(api, "get_json", fake)
    search.fetch_expenditures(17436)

    assert seen["SearchTypeCategory"] == search.CATEGORY_EXPENDITURES == "B"
    assert seen["CpfId"] == 17436


def test_looks_like_receipt_shape_detection():
    assert search._looks_like_receipt({"contributorCpfId": 1})
    assert search._looks_like_receipt({"fullNameReverse": "X"})
    # A vendor key settles it as an expenditure even when a name field rides along.
    assert not search._looks_like_receipt({"vendor": "X", "fullNameReverse": "Y"})
    assert not search._looks_like_receipt({"vendor": "X"})


# --- 2.5 amount and date parsing ---


def test_annotate_parses_amounts_and_dates():
    items = search.annotate(
        [
            {"amount": "$1,234.56", "date": "1/22/2020"},
            {"amount": "$0.00", "date": "12/5/2026"},
            {"amount": "not money", "date": "not a date"},
            {"amount": None, "date": None},
        ]
    )

    assert items[0]["amountValue"] == 1234.56
    assert items[0]["dateValue"] == date(2020, 1, 22)
    assert items[1]["amountValue"] == 0.0
    assert items[1]["dateValue"] == date(2026, 12, 5)
    # Malformed input degrades to a zero amount and a null date rather than raising.
    assert items[2]["amountValue"] == 0.0
    assert items[2]["dateValue"] is None
    assert items[3]["amountValue"] == 0.0
    assert items[3]["dateValue"] is None


def test_parse_date_rejects_out_of_range():
    assert search._parse_date("13/45/2026") is None
    assert search._parse_date("1/2") is None
    assert search._parse_date(12345) is None
