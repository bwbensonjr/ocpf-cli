"""Tests for district resolution, including the near-collision case."""

from __future__ import annotations

import pytest

from ocpf_cli import districts
from ocpf_cli.districts import (
    District,
    DistrictResolutionError,
    resolve_district,
    _normalize,
)

# Captured before the autouse fixture can stub it, for the one test that
# exercises this function directly.
REAL_DISTRICT_FOR_CODE = districts._district_for_code


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Keep resolution's network tiers out of tests that only exercise tier 1.

    `resolve_district` now falls through to the year's feed and, for older
    years, a code-range sweep. Both are real HTTP; a test that means to exercise
    them overrides these stubs explicitly.
    """
    monkeypatch.setattr(districts, "fetch_year_districts", lambda year: [])
    # Stub the leaf that makes requests, not the sweep itself, so tests that
    # mean to exercise the sweep still run the real traversal.
    monkeypatch.setattr(districts, "_district_for_code", lambda year, code: None)


# A small fixture set covering the near-collision and the ambiguous prefix.
DISTRICTS = [
    District(code=151, office="Senate", description="Middlesex & Suffolk"),
    District(code=166, office="Senate", description="Suffolk and Middlesex"),
    District(code=115, office="Senate", description="1st Middlesex"),
    District(code=116, office="Senate", description="2nd Middlesex"),
    District(code=201, office="House", description="1st Barnstable"),
]


def test_numeric_code_resolves_directly():
    assert resolve_district("166", 2026, DISTRICTS).code == 166


def test_invalid_numeric_code_errors():
    with pytest.raises(DistrictResolutionError):
        resolve_district("99999", 2026, DISTRICTS)


def test_suffolk_and_middlesex_resolves_to_166():
    assert resolve_district("Suffolk and Middlesex", 2026, DISTRICTS).code == 166


def test_ampersand_and_word_and_are_equivalent():
    assert resolve_district("Suffolk & Middlesex", 2026, DISTRICTS).code == 166


def test_near_collision_middlesex_and_suffolk_resolves_to_151():
    assert resolve_district("Middlesex & Suffolk", 2026, DISTRICTS).code == 151
    assert resolve_district("Middlesex and Suffolk", 2026, DISTRICTS).code == 151


def test_case_insensitive_match():
    assert resolve_district("suffolk AND middlesex", 2026, DISTRICTS).code == 166


def test_ambiguous_middlesex_lists_candidates():
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Middlesex", 2026, DISTRICTS)
    codes = {c.code for c in exc.value.candidates}
    # All four Middlesex-bearing districts collide on the bare word.
    assert codes == {151, 166, 115, 116}


def test_no_match_errors_without_candidates():
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Nonexistent County", 2026, DISTRICTS)
    assert exc.value.candidates == []


# --- ordinal folding ---


def test_ordinal_words_fold_to_digits():
    assert _normalize("First Plymouth & Norfolk") == _normalize("1st Plymouth and Norfolk")
    assert _normalize("Second Plymouth and Norfolk") == "2nd plymouth and norfolk"
    assert _normalize("Third Barnstable") == "3rd barnstable"


def test_compound_ordinals_fold_in_both_spellings():
    assert _normalize("Twenty-First Middlesex") == "21st middlesex"
    assert _normalize("twenty first middlesex") == "21st middlesex"
    assert _normalize("Thirty-Seventh Middlesex") == "37th middlesex"


def test_teen_ordinals_take_a_th_suffix():
    assert _normalize("Eleventh Suffolk") == "11th suffolk"
    assert _normalize("Twelfth Essex") == "12th essex"
    assert _normalize("Twentieth Middlesex") == "20th middlesex"


def test_folding_does_not_disturb_word_order():
    # Order still distinguishes two real districts.
    assert _normalize("Middlesex & Suffolk") != _normalize("Suffolk and Middlesex")


def test_folding_does_not_match_inside_a_word():
    # No ordinal word is a substring of a county name, but guard the boundary.
    assert _normalize("Firstbrook") == "firstbrook"
    assert _normalize("Worcester") == "worcester"


def test_ordinal_word_resolves_a_district():
    # "Second Middlesex" reaches 2nd Middlesex, which the digit form also reaches.
    assert resolve_district("Second Middlesex", 2026, DISTRICTS).code == 116
    assert resolve_district("2nd Middlesex", 2026, DISTRICTS).code == 116


# --- year-aware resolution ---


def test_year_is_required():
    # Resolving without a year would silently use the current map, which is the
    # class of error year-awareness exists to remove.
    with pytest.raises(TypeError):
        resolve_district("Suffolk and Middlesex")


def test_tier_one_short_circuits_without_further_requests(monkeypatch):
    calls: list = []

    def fake_year(year):
        calls.append(("feed", year))
        return []

    def fake_sweep(year, target):
        calls.append(("sweep", year))
        return None

    monkeypatch.setattr(districts, "fetch_year_districts", fake_year)
    monkeypatch.setattr(districts, "sweep_historical_districts", fake_sweep)

    assert resolve_district("Suffolk and Middlesex", 2013, DISTRICTS).code == 166
    assert calls == []


def test_current_map_resolution_is_unchanged_across_years(monkeypatch):
    for year in (2010, 2020, 2026):
        assert resolve_district("Suffolk and Middlesex", year, DISTRICTS).code == 166


# --- officeSought parsing ---


def test_parse_office_sought_comma_and_ampersand():
    assert districts._parse_office_sought("Senate, Worcester & Norfolk") == (
        "Senate",
        "Worcester & Norfolk",
    )
    assert districts._parse_office_sought("House, 6th Bristol") == ("House", "6th Bristol")


def test_parse_office_sought_without_a_comma():
    assert districts._parse_office_sought("House 28th Middlesex") == (
        "House",
        "28th Middlesex",
    )


def test_parse_office_sought_rejects_non_legislative_and_empty():
    assert districts._parse_office_sought("Mayoral, Boston") is None
    assert districts._parse_office_sought("Senate") is None
    assert districts._parse_office_sought("") is None


# --- tier 2: the year's feed ---


RETIRED = District(code=140, office="Senate", description="Worcester & Norfolk")


def test_retired_district_resolves_for_a_year_it_existed(monkeypatch):
    monkeypatch.setattr(
        districts, "fetch_year_districts", lambda year: [RETIRED] if year == 2020 else []
    )
    resolved = resolve_district("Worcester and Norfolk", 2020, DISTRICTS)
    assert resolved.code == 140
    assert resolved.office == "Senate"


def test_feed_tier_is_skipped_before_its_first_year(monkeypatch):
    seen: list = []
    monkeypatch.setattr(districts, "fetch_merged_field", lambda year: seen.append(year) or [], raising=False)
    # fetch_year_districts returns early for pre-feed years without fetching.
    assert districts.fetch_year_districts(2013) == []


def test_feed_tier_ambiguity_is_not_guessed(monkeypatch):
    twins = [
        District(code=140, office="Senate", description="Worcester & Norfolk"),
        District(code=141, office="House", description="Worcester & Norfolk"),
    ]
    monkeypatch.setattr(districts, "fetch_year_districts", lambda year: twins)
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Worcester and Norfolk", 2020, DISTRICTS)
    assert len(exc.value.candidates) == 2


# --- tier 3: the historical sweep ---


def test_sweep_runs_only_for_years_the_feed_does_not_cover(monkeypatch):
    swept: list = []
    monkeypatch.setattr(districts, "fetch_year_districts", lambda year: [])
    monkeypatch.setattr(
        districts, "sweep_historical_districts", lambda year, target: swept.append(year) or None
    )
    for year in (2020, 2026):
        with pytest.raises(DistrictResolutionError):
            resolve_district("Worcester and Norfolk", year, DISTRICTS)
    assert swept == []

    with pytest.raises(DistrictResolutionError):
        resolve_district("Worcester and Norfolk", 2010, DISTRICTS)
    assert swept == [2010]


def test_sweep_resolves_from_a_historical_code(monkeypatch):
    monkeypatch.setattr(districts, "fetch_year_districts", lambda year: [])
    monkeypatch.setattr(
        districts, "sweep_historical_districts", lambda year, target: RETIRED
    )
    assert resolve_district("Worcester and Norfolk", 2010, DISTRICTS).code == 140


def test_sweep_visits_senate_before_house(monkeypatch):
    order: list = []

    def fake_for_code(year, code):
        order.append(code)
        return None

    monkeypatch.setattr(districts, "_district_for_code", fake_for_code)
    districts.sweep_historical_districts(2010, "nothing matches")
    senate_codes = [c for c in order if c in districts.OFFICE_CODE_RANGES["Senate"]]
    house_codes = [c for c in order if c in districts.OFFICE_CODE_RANGES["House"]]
    assert senate_codes and house_codes
    assert order.index(senate_codes[0]) < order.index(house_codes[0])


def test_sweep_stops_at_the_first_match(monkeypatch):
    visited: list = []

    def fake_for_code(year, code):
        visited.append(code)
        if code == 140:
            return RETIRED
        return None

    monkeypatch.setattr(districts, "_district_for_code", fake_for_code)
    found = districts.sweep_historical_districts(2010, districts._normalize("Worcester and Norfolk"))
    assert found is RETIRED
    assert visited[-1] == 140
    # It stopped rather than continuing through the rest of the Senate range.
    assert max(visited) == 140


def test_district_for_code_prefers_the_label_most_filers_report(monkeypatch):
    payloads = {
        1: {"officeSought": {"districtCode": 140, "officeDescription": "Senate",
                             "districtDescription": "Worcester & Norfolk"}},
        2: {"officeSought": {"districtCode": 140, "officeDescription": "Senate",
                             "districtDescription": "Worcester & Norfolk"}},
        # A filer who last sought a different seat cannot label this one.
        3: {"officeSought": {"districtCode": 999, "officeDescription": "Senate",
                             "districtDescription": "Somewhere Else"}},
    }
    import ocpf_cli.legislative as legislative

    monkeypatch.setattr(legislative, "fetch_finsummaries", lambda y, c: [{"cpfId": 1}, {"cpfId": 2}, {"cpfId": 3}])
    monkeypatch.setattr(
        districts.api, "get_json", lambda path, params=None, **kw: payloads[int(path.split("/")[-1])]
    )
    found = REAL_DISTRICT_FOR_CODE(2010, 140)
    assert found is not None
    assert (found.code, found.description) == (140, "Worcester & Norfolk")


# --- error messages ---


def test_error_names_the_year_when_the_district_existed_elsewhere(monkeypatch):
    monkeypatch.setattr(
        districts, "fetch_year_districts", lambda year: [RETIRED] if year == 2020 else []
    )
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Worcester and Norfolk", 2026, DISTRICTS)
    message = str(exc.value)
    assert "was not a legislative district in 2026" in message
    assert "2020" in message
    assert "140" in message


def test_error_for_a_name_that_was_never_a_district(monkeypatch):
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Nonexistent County", 2026, DISTRICTS)
    message = str(exc.value)
    assert "matches no legislative" in message
    assert "2026" in message


def test_error_mentions_the_current_map_when_the_name_is_current(monkeypatch):
    # Resolving a current district for a year before it existed: tier 1 is
    # bypassed by an empty current list, so the explanation must still find it.
    monkeypatch.setattr(districts, "fetch_year_districts", lambda year: [])
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Suffolk and Middlesex", 2010, [])
    assert "matches no legislative" in str(exc.value)
