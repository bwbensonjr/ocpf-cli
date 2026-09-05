"""Filer resolution: turn a user-supplied argument into a single `cpfId`.

Shared by the commands that operate on one filer (`ocpf filer`,
`ocpf expenditures`) so the resolution contract — numeric cpfId for any filer
type, legislative name match otherwise, never guess when ambiguous — is stated
once. Command modules import from here rather than from each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from .legislative import fetch_merged_field


@dataclass(frozen=True)
class FilerMatch:
    """A candidate name match from the legislative field."""

    cpf_id: int
    name: str
    office: str


class FilerResolutionError(Exception):
    """Name resolution failed. `matches` is populated for the ambiguous case."""

    def __init__(self, message: str, *, matches: list[FilerMatch] | None = None) -> None:
        super().__init__(message)
        self.matches = matches or []


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for forgiving name matching."""
    return " ".join(text.lower().split())


def resolve_filer(query: str, year: int) -> int:
    """Resolve `query` to a single `cpfId`.

    A bare integer is used directly (works for any filer type). Otherwise the
    value is matched case-insensitively against `filerName` in the legislative
    field for `year`; ambiguity is never guessed away.
    """
    stripped = query.strip()
    if stripped.lstrip("-").isdigit():
        return int(stripped)

    target = _normalize(query)
    field = fetch_merged_field(year)
    matches = [
        FilerMatch(
            cpf_id=row.get("cpfId"),
            name=row.get("filerName", ""),
            office=row.get("officeSought", ""),
        )
        for row in field
        if target in _normalize(row.get("filerName", ""))
    ]

    if len(matches) == 1:
        return matches[0].cpf_id
    if len(matches) == 0:
        raise FilerResolutionError(
            f'"{query}" matches no legislative filer for {year}; '
            f"pass a numeric cpfId directly to look up any filer"
        )
    raise FilerResolutionError(
        f'"{query}" matches more than one legislative filer',
        matches=matches,
    )
