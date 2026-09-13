"""District resolution: turn a `<district>` argument into one OCPF code.

Resolution is district-first (the API's free-text filer search is dead) and
**year-aware**: a name resolves to the code that district held in the requested
year, so a district retired at redistricting stays reachable for the years it
existed. Ambiguity is never guessed away.

The `districts` reference is strictly the present map — 365 rows, 200
legislative (160 House, 40 Senate) — and it omits retired codes entirely: code
140, Senate Worcester & Norfolk through the 2011 cycle, appears under no office.
There is no year-scoped list to fall back on; `districts/{year}` returns `[]` and
`onballot/districts/{year}` is a 404. So resolution works in tiers, cheapest
first:

1. **The current `districts` reference.** Today's behavior exactly. If it
   answers, nothing else is consulted and no extra request is made.
2. **The legislative YTD feed for the year**, which carries an era-correct
   `officeSought` string *and* a usable `districtCodeSought` on every row —
   verified for 2020, where "Senate, Worcester & Norfolk" pairs with code 140 and
   no office string maps to two codes. `ocpf race` fetches this field anyway.
   Feed coverage starts abruptly at 2020 (428 rows; 2019 has 13, 2018 has 2), so
   this tier stops there.
3. **The special-election report log**, which names the seats that held a
   special in the year from the filings themselves. This is the only tier that
   answers for a pre-2020 **odd** year: `onballot/finsummaries` returns nothing
   for 2007, 2013, 2015, 2017, 2019 or 2020+, and tier 2 starts at 2020, so those
   years fall between them. Seeded from the memoized sweep in `reports.py`, so it
   answers only for seats that held a special and is nearly free once `--special`
   has fetched it. Log rows carry no district code; see `_code_from_filers`.
4. **A sweep of the office's code range** via `onballot/finsummaries/{year}/{code}`,
   labelling each populated code from `filer/{cpfId}.officeSought`. Expensive (76
   probes for Senate, 164 for House, plus one filer lookup per populated code),
   so it is last and lazy, and it only answers for a year `finsummaries` covers.

A resolved district may carry **no code**. Tier 3 can name a seat the API will
not number, because `filer/{cpfId}` reports a filer's most recent office and a
roster whose filers have all moved on says nothing about the seat they once
sought. Such a district still resolves — reporting it as non-existent because
only its number is unknown would be a worse answer than omitting the number.
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
    """A single legislative district, as some source named it for some year.

    `code` is optional because the sources that can *name* a district and those
    that can *code* it are not the same set. The report-log tier knows what a
    seat was called in a year from the filings themselves, but a log row carries
    no district code; the code is recovered from the filers who sought the seat,
    and a roster whose filers have all since sought something else yields none.
    Such a district still resolves, without a code, rather than being reported as
    one that never existed. See `resolve_district`.
    """

    code: int | None
    office: str
    description: str

    @property
    def label(self) -> str:
        """Human label, e.g. `Senate, Suffolk and Middlesex`."""
        return f"{self.office}, {self.description}"

    @property
    def full_label(self) -> str:
        """`Senate, 1st Suffolk (code 130)`, dropping the code when unknown.

        Every place that names a district to the user goes through this, so an
        absent code reads as an omission rather than as `code None`.
        """
        if self.code is None:
            return self.label
        return f"{self.label} (code {self.code})"


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


# The legislative YTD feed only carries rows from this year on; before it, tier
# 2 has nothing to match against. Measured: 428 rows in 2020, 13 in 2019, 2 in
# 2018, 0 in 2017.
FIRST_FEED_YEAR = 2020

# Code ranges to sweep in tier 3. Wider than the current map (Senate 105-170,
# House 201-364) because retired codes fall outside it — Senate 140 is within
# range here but absent from the reference entirely, and Senate 104 (1st
# Plymouth & Bristol through the 2020 cycle) falls *below* its floor. A range
# widened only at the top misses that one: 104 is populated in every year
# `finsummaries` covers, so a pre-2021 query for that seat failed the sweep
# without ever probing it. Nothing below 104 or between 171 and 200 is
# populated, and nothing at 365+, so the floors and ceilings here are measured,
# not padded.
OFFICE_CODE_RANGES = {
    # Senate first: less than half the probes, and retired-district queries skew
    # Senate (every 2011-cycle district that fails a current-map lookup is one).
    "Senate": range(104, 181),
    "House": range(201, 365),
}


def _parse_office_sought(text: str) -> tuple[str, str] | None:
    """Split an `officeSought` string into (office, description).

    The feed writes `"Senate, Worcester & Norfolk"`; other endpoints write the
    same thing without a comma (`"House 28th Middlesex"`). Returns None when the
    office is not legislative.
    """
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return None
    office, sep, description = cleaned.partition(",")
    if not sep:
        # No comma: the office is the leading word, the rest is the district.
        office, _, description = cleaned.partition(" ")
    office = office.strip()
    description = description.strip()
    if office not in LEGISLATIVE_OFFICES or not description:
        return None
    return office, description


def fetch_year_districts(year: int) -> list[District]:
    """Districts as the legislative feed named them in `year` (tier 2).

    Every feed row pairs an era-correct `officeSought` with a `districtCodeSought`,
    so this needs no per-filer lookups. Returns an empty list for years the feed
    does not cover.
    """
    if year < FIRST_FEED_YEAR:
        return []

    from .legislative import fetch_merged_field

    by_code: dict[int, District] = {}
    for row in fetch_merged_field(year):
        code = row.get("districtCodeSought")
        if not isinstance(code, int) or code <= 0:
            continue
        parsed = _parse_office_sought(row.get("officeSought") or "")
        if parsed is None:
            continue
        office, description = parsed
        by_code.setdefault(code, District(code=code, office=office, description=description))
    return list(by_code.values())


def _district_for_code(year: int, code: int) -> District | None:
    """Name the district at `code` in `year` from the filers who sought it.

    `onballot/finsummaries` rows carry `districtCode: 0` and no district name, so
    the code is known only from the URL that produced it and the name only from
    the filers it lists. `filer/{cpfId}.officeSought` retains both — verified for
    cpfId 10315, which still reports code 140 / "Worcester & Norfolk" a decade
    after that seat was retired.

    When a code's filers disagree (someone who changed districts), the label the
    most of them report wins.
    """
    from .legislative import fetch_finsummaries

    try:
        rows = fetch_finsummaries(year, code) or []
    except api.OcpfApiError:
        return None

    cpf_ids = [row.get("cpfId") for row in rows if row.get("cpfId")]
    if not cpf_ids:
        # No roster means no evidence this code was contested that year. Return
        # before the fallback below, which must not cost a request on the empty
        # codes that make up most of the swept range.
        return None

    tally: dict[tuple[str, str], int] = {}
    for cpf_id in cpf_ids:
        try:
            payload = api.get_json(f"filer/{cpf_id}")
        except api.OcpfApiError:
            continue
        sought = (payload or {}).get("officeSought") or {}
        if sought.get("districtCode") != code:
            # This filer last sought a different seat; it cannot label this one.
            continue
        office = (sought.get("officeDescription") or "").strip()
        description = (sought.get("districtDescription") or "").strip()
        if office in LEGISLATIVE_OFFICES and description:
            key = (office, description)
            tally[key] = tally.get(key, 0) + 1

    if not tally:
        # Every filer on the roster has since sought a different seat, so none
        # of them can name this one. The code is still certain -- it is the URL
        # that just returned this roster -- so only the name is missing, and the
        # filings themselves still carry it.
        return _district_from_filings(year, code, cpf_ids)

    (office, description), _ = max(tally.items(), key=lambda kv: kv[1])
    return District(code=code, office=office, description=description)


def _district_from_filings(
    year: int, code: int, cpf_ids: list[int]
) -> District | None:
    """Name `code` from what its roster's filings for `year` called the seat.

    Reached only when `_district_for_code`'s filer tally came up empty, which
    happens whenever every candidate who sought the seat has since sought a
    different one. Senate 104 is the live case: it is populated in every year
    `finsummaries` covers, but only 2010 and 2011 have a filer who stayed put,
    so the four remaining years were unresolvable on the filer tally alone.

    `reports.offices_sought_in_year` is era-correct where
    `filer/{cpfId}.officeSought` is not. Tallying across the whole roster rather
    than trusting one filer keeps a candidate who switched seats mid-year from
    naming the seat by themselves.

    Returns None when the filings name nothing legislative for the year. That is
    an absence of evidence, not proof the district did not exist: the caller
    must not report it as a district that never was.
    """
    from . import reports

    tally: dict[tuple[str, str], int] = {}
    for cpf_id in cpf_ids:
        try:
            offices = reports.offices_sought_in_year(cpf_id, year)
        except api.OcpfApiError:
            continue
        for office_sought in offices:
            parsed = _parse_office_sought(office_sought)
            if parsed is None:
                continue
            tally[parsed] = tally.get(parsed, 0) + 1

    if not tally:
        return None
    (office, description), _ = max(tally.items(), key=lambda kv: kv[1])
    return District(code=code, office=office, description=description)


def sweep_historical_districts(year: int, target: str) -> District | None:
    """Find the district named `target` in `year` by sweeping code ranges (tier 3).

    Returns as soon as a code's label matches, so the average cost is far below
    the worst case. `target` is already normalized.
    """
    from . import render

    for office, codes in OFFICE_CODE_RANGES.items():
        render.status(f"Searching {office} districts for {year}...")
        for code in codes:
            found = _district_for_code(year, code)
            if found is not None and _normalize(found.description) == target:
                return found
    return None


# --------------------------------------------------------------------------
# Tier 3: the special-election report log
# --------------------------------------------------------------------------


def fetch_log_seats(year: int) -> dict[tuple[str, str], set[int]]:
    """Seats that held a special election in `year`, mapped to the cpfIds that
    filed for them, named as the filings named them.

    Seeded from the memoized special-election sweep in `reports`, whose rows pair
    an era-correct `officeSought` with a parsed reporting period. This is the
    only source that answers for a year no code source covers -- `finsummaries`
    returns nothing for 2007, 2013, 2015, 2017, 2019 or 2020+, and the
    legislative feed starts at 2020.

    Carries no district code: a log row has none, and recovering one costs a
    request per filer, so that is left to `_code_from_filers` for the seat
    actually asked about.
    """
    from . import reports

    seats: dict[tuple[str, str], set[int]] = {}
    for stage in reports.SpecialStage:
        for row in reports.fetch_special_reports(stage):
            parsed = _parse_office_sought(row.office_sought)
            if parsed is None:
                # The sweep also carries municipal, mayoral and Governor's
                # Council specials; this tier is legislative like the rest.
                continue
            if row.period is None or row.period.end.year != year:
                continue
            office, description = parsed
            seats.setdefault((office, description), set()).add(row.cpf_id)
    return seats


def fetch_log_districts(year: int) -> list[District]:
    """The log's seats for `year` as `District`s, without codes.

    Names only. Codes are recovered per seat, after matching, by
    `resolve_from_log` -- recovering them for every seat in the year would cost
    a filer lookup per candidate across every special held that year (roughly
    forty requests for 2013) to answer about one district.
    """
    return [
        District(code=None, office=office, description=description)
        for office, description in fetch_log_seats(year)
    ]


def resolve_from_log(year: int, target: str, query: str) -> District | None:
    """Resolve `target` against the log's seats for `year`, code and all.

    Matching is exact (see `_match_exact`); the code is recovered only for the
    seats that actually matched, which is one in the normal case and a handful
    in the ambiguous one.
    """
    seats = fetch_log_seats(year)
    matches = _match_exact(
        [District(code=None, office=o, description=d) for o, d in seats], target
    )
    if not matches:
        return None

    coded = [
        District(
            code=_code_from_filers(
                d.office, d.description, seats[(d.office, d.description)]
            ),
            office=d.office,
            description=d.description,
        )
        for d in matches
    ]
    if len(coded) == 1:
        return coded[0]
    raise _ambiguous(query, coded)


def _code_from_filers(office: str, description: str, cpf_ids: set[int]) -> int | None:
    """Recover a seat's district code from the filers who sought it.

    `filer/{cpfId}.officeSought` reports a filer's MOST RECENT office, not the
    one they sought in the year in question, so this is a tally rather than a
    lookup. A filer whose reported district no longer matches the seat is
    discarded: Brady (14822) and Diehl (14907) both filed for Senate 2nd Plymouth
    & Bristol in 2015 and both now report *2nd Plymouth and Norfolk* (code 169),
    so trusting the modal code without checking the description would return the
    wrong district entirely.

    Returns None when no filer still names the seat, which is a real case --
    Senate 1st Hampden & Hampshire 2013 has one filer in the sweep and they have
    since sought a Governor's Council seat.
    """
    target = _normalize(description)
    tally: dict[int, int] = {}
    for cpf_id in sorted(cpf_ids):
        try:
            payload = api.get_json(f"filer/{cpf_id}")
        except api.OcpfApiError:
            continue
        sought = (payload or {}).get("officeSought") or {}
        code = sought.get("districtCode")
        if not isinstance(code, int):
            continue
        if (sought.get("officeDescription") or "").strip() != office:
            continue
        if _normalize((sought.get("districtDescription") or "").strip()) != target:
            continue
        tally[code] = tally.get(code, 0) + 1

    if not tally:
        return None
    return max(tally.items(), key=lambda kv: kv[1])[0]


def _match(districts: list[District], target: str) -> list[District]:
    """Exact normalized matches, falling back to substring matches."""
    exact = [d for d in districts if _normalize(d.description) == target]
    if exact:
        return exact
    return [d for d in districts if target in _normalize(d.description)]


def _match_exact(districts: list[District], target: str) -> list[District]:
    """Exact normalized matches only -- no substring fallback.

    Used by the log tier, where a substring fallback is unsafe: the tier sees
    only the seats that held a special in one year, so if that set contains
    `21st Suffolk` and not `1st Suffolk`, a substring match would resolve a
    request for the latter to the former with nothing to signal the swap. The
    higher tiers can afford the fallback because they see the whole map, where
    an exact match for such a name exists and wins first.
    """
    return [d for d in districts if _normalize(d.description) == target]


def _ambiguous(query: str, matches: list[District]) -> DistrictResolutionError:
    return DistrictResolutionError(
        f'"{query}" matches more than one legislative district',
        candidates=matches,
    )


def resolve_district(
    query: str,
    year: int,
    districts: list[District] | None = None,
) -> District:
    """Resolve `query` to the district it named in `year`.

    `year` is required rather than defaulting, so a caller cannot resolve a 2013
    query against the current map by omission — the class of error this
    year-awareness exists to remove.

    Raises `DistrictResolutionError` on no match or ambiguous match (with the
    candidate list attached), so the caller can print options without guessing.
    """
    if districts is None:
        districts = fetch_legislative_districts()

    by_code = {d.code: d for d in districts if d.code is not None}

    # A bare integer is treated as a raw district code.
    stripped = query.strip()
    if stripped.lstrip("-").isdigit():
        code = int(stripped)
        if code in by_code:
            return by_code[code]
        historical = _district_for_code(year, code)
        if historical is not None:
            return historical
        raise DistrictResolutionError(
            f"{code} is not a legislative (House/Senate) district code in {year}"
        )

    target = _normalize(query)

    # Tier 1: the current map. Short-circuits with no extra request.
    matches = _match(districts, target)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise _ambiguous(query, matches)

    # Tier 2: the year's feed, which names districts as they stood then.
    year_districts = fetch_year_districts(year)
    matches = _match(year_districts, target)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise _ambiguous(query, matches)

    # Tier 3: the special-election log, which names seats for the years no code
    # source covers. Memoized, so this is nearly free once `--special` has run,
    # and it runs before the code-range sweep so the years it answers for stop
    # paying that sweep's ~20-30 seconds.
    found = resolve_from_log(year, target, query)
    if found is not None:
        return found

    # Tier 4: sweep the code ranges for a year the feed does not cover.
    if year < FIRST_FEED_YEAR:
        found = sweep_historical_districts(year, target)
        if found is not None:
            return found

    raise _no_match_error(query, target, year, districts)


def _no_match_error(
    query: str,
    target: str,
    year: int,
    districts: list[District],
) -> DistrictResolutionError:
    """Explain a failure in terms of the requested year, not the current map.

    Three distinct cases, because saying "matches no legislative district" about
    a name that was one for twenty years is the bug this change fixes. To say
    where a name *is* known without an open-ended search, this checks the current
    map and the earliest year the feed covers — both cheap and usually already
    fetched.
    """
    elsewhere: list[str] = []

    current = _match(districts, target)
    if current:
        where = ", ".join(d.full_label for d in current[:3])
        elsewhere.append(f"the current map has {where}")

    if year != FIRST_FEED_YEAR:
        try:
            earlier = _match(fetch_year_districts(FIRST_FEED_YEAR), target)
        except api.OcpfApiError:
            earlier = []
        if earlier:
            where = ", ".join(d.full_label for d in earlier[:3])
            elsewhere.append(f"it existed in {FIRST_FEED_YEAR} as {where}")

    if elsewhere:
        return DistrictResolutionError(
            f'"{query}" was not a legislative district in {year}; '
            + "; ".join(elsewhere)
        )

    return DistrictResolutionError(
        f'"{query}" matches no legislative (House/Senate) district in {year}'
    )
