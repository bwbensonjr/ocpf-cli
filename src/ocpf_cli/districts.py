"""District resolution: turn a `<district>` argument into one OCPF code.

Resolution is district-first (the API's free-text filer search is dead). A raw
numeric code is validated against the legislative set; otherwise the name is
matched case-insensitively against district descriptions, restricted to
legislative offices (House and Senate). Ambiguity is never guessed away.
"""

from __future__ import annotations

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


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, and treat `&` and `and` alike.

    So `"Suffolk and Middlesex"` and `"Suffolk & Middlesex"` normalize to the
    same string, while `"Middlesex & Suffolk"` stays distinct (order matters).
    """
    lowered = text.lower().replace("&", " and ")
    return " ".join(lowered.split())


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
