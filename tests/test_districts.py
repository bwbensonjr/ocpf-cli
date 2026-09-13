"""Tests for district resolution, including the near-collision case."""

from __future__ import annotations

import pytest

from ocpf_cli.districts import (
    District,
    DistrictResolutionError,
    resolve_district,
    _normalize,
)

# A small fixture set covering the near-collision and the ambiguous prefix.
DISTRICTS = [
    District(code=151, office="Senate", description="Middlesex & Suffolk"),
    District(code=166, office="Senate", description="Suffolk and Middlesex"),
    District(code=115, office="Senate", description="1st Middlesex"),
    District(code=116, office="Senate", description="2nd Middlesex"),
    District(code=201, office="House", description="1st Barnstable"),
]


def test_numeric_code_resolves_directly():
    assert resolve_district("166", DISTRICTS).code == 166


def test_invalid_numeric_code_errors():
    with pytest.raises(DistrictResolutionError):
        resolve_district("99999", DISTRICTS)


def test_suffolk_and_middlesex_resolves_to_166():
    assert resolve_district("Suffolk and Middlesex", DISTRICTS).code == 166


def test_ampersand_and_word_and_are_equivalent():
    assert resolve_district("Suffolk & Middlesex", DISTRICTS).code == 166


def test_near_collision_middlesex_and_suffolk_resolves_to_151():
    assert resolve_district("Middlesex & Suffolk", DISTRICTS).code == 151
    assert resolve_district("Middlesex and Suffolk", DISTRICTS).code == 151


def test_case_insensitive_match():
    assert resolve_district("suffolk AND middlesex", DISTRICTS).code == 166


def test_ambiguous_middlesex_lists_candidates():
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Middlesex", DISTRICTS)
    codes = {c.code for c in exc.value.candidates}
    # All four Middlesex-bearing districts collide on the bare word.
    assert codes == {151, 166, 115, 116}


def test_no_match_errors_without_candidates():
    with pytest.raises(DistrictResolutionError) as exc:
        resolve_district("Nonexistent County", DISTRICTS)
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
    assert resolve_district("Second Middlesex", DISTRICTS).code == 116
    assert resolve_district("2nd Middlesex", DISTRICTS).code == 116
