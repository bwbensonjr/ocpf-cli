"""District resolution: turn a `<district>` argument into one OCPF code.

Resolution is district-first (the API's free-text filer search is dead). A raw
numeric code is validated against the legislative set; otherwise the name is
matched case-insensitively against district descriptions, restricted to
legislative offices (House and Senate). Ambiguity is never guessed away.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from . import api

# Office values in the `districts` reference that count as legislative.
LEGISLATIVE_OFFICES = ("House", "Senate")


@dataclass(frozen=True)
class District:
    """A single legislative district from the OCPF `districts` reference."""

    code: int
    office: str
    description: str

    @property
    def label(self) -> str:
        """Human label, e.g. `Senate, Suffolk and Middlesex`."""
        return f"{self.office}, {self.description}"


class DistrictResolutionError(Exception):
    """Resolution failed. `candidates` is populated for the ambiguous case."""

    def __init__(
        self, message: str, *, candidates: list[District] | None = None
    ) -> None:
        super().__init__(message)
        self.candidates = candidates or []


def _ordinal_suffix(n: int) -> str:
    """The English suffix for `n`: 1 -> st, 2 -> nd, 3 -> rd, 11 -> th."""
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _build_ordinal_words() -> dict[str, str]:
    """Map ordinal words to the digit forms the API uses: `first` -> `1st`.

    Covers 1-40, which spans every numbered House (up to 37th) and Senate
    district. Compound ordinals are registered in both the hyphenated and the
    spaced spelling, since sources differ and `_normalize` does not join words.
    """
    units = [
        "first", "second", "third", "fourth", "fifth",
        "sixth", "seventh", "eighth", "ninth",
    ]
    teens = [
        "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth",
        "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth",
    ]
    tens_ordinal = {20: "twentieth", 30: "thirtieth", 40: "fortieth"}
    tens_cardinal = {20: "twenty", 30: "thirty", 40: "forty"}

    words: dict[str, str] = {}
    for i, word in enumerate(units, start=1):
        words[word] = f"{i}{_ordinal_suffix(i)}"
    for i, word in enumerate(teens, start=10):
        words[word] = f"{i}{_ordinal_suffix(i)}"
    for base, word in tens_ordinal.items():
        words[word] = f"{base}{_ordinal_suffix(base)}"
    for base, prefix in tens_cardinal.items():
        for i, unit in enumerate(units, start=1):
            value = base + i
            if value > 40:
                continue
            digits = f"{value}{_ordinal_suffix(value)}"
            words[f"{prefix}-{unit}"] = digits
            words[f"{prefix} {unit}"] = digits
    return words


ORDINAL_WORDS = _build_ordinal_words()

# Longest first, so `twenty-first` is consumed before `first` can match inside
# it. Word boundaries keep `first` from matching inside an unrelated word.
_ORDINAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(ORDINAL_WORDS, key=len, reverse=True)) + r")\b"
)


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, treat `&` and `and` alike, fold ordinals.

    So `"Suffolk and Middlesex"` and `"Suffolk & Middlesex"` normalize to the
    same string, while `"Middlesex & Suffolk"` stays distinct (order matters).

    Ordinal words fold to the digit forms the API writes: `"First Plymouth &
    Norfolk"` and `"1st Plymouth and Norfolk"` normalize alike. The fold is
    one-directional because OCPF always writes digits, so digits are canonical.
    """
    lowered = text.lower().replace("&", " and ")
    collapsed = " ".join(lowered.split())
    return _ORDINAL_RE.sub(lambda m: ORDINAL_WORDS[m.group(0)], collapsed)


def fetch_legislative_districts() -> list[District]:
    """Fetch the `districts` reference and keep only House/Senate offices."""
    raw: Any = api.get_json("districts")
    districts = []
    for row in raw:
        office = row.get("office", "")
        if office in LEGISLATIVE_OFFICES:
            districts.append(
                District(
                    code=int(row["code"]),
                    office=office,
                    description=row.get("description", ""),
                )
            )
    return districts


def resolve_district(
    query: str, districts: list[District] | None = None
) -> District:
    """Resolve `query` to exactly one legislative `District`.

    Raises `DistrictResolutionError` on no match or ambiguous match (with the
    candidate list attached), so the caller can print options without guessing.
    """
    if districts is None:
        districts = fetch_legislative_districts()

    by_code = {d.code: d for d in districts}

    # A bare integer is treated as a raw district code.
    stripped = query.strip()
    if stripped.lstrip("-").isdigit():
        code = int(stripped)
        if code in by_code:
            return by_code[code]
        raise DistrictResolutionError(
            f"{code} is not a legislative (House/Senate) district code"
        )

    target = _normalize(query)

    # Prefer an exact normalized-name match; fall back to substring matches.
    exact = [d for d in districts if _normalize(d.description) == target]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise DistrictResolutionError(
            f'"{query}" matches more than one legislative district',
            candidates=exact,
        )

    matches = [d for d in districts if target in _normalize(d.description)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        raise DistrictResolutionError(
            f'"{query}" matches no legislative (House/Senate) district'
        )
    raise DistrictResolutionError(
        f'"{query}" matches more than one legislative district',
        candidates=matches,
    )
