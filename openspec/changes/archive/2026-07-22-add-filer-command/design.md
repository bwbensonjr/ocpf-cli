## Context

`ocpf` already has a working `cli-foundation` (API client, table/JSON rendering,
exit codes) and a `race` command that lists the candidates in a legislative
district, one row per `cpfId`. This change adds `ocpf filer`, the drill-down
companion that turns a single `cpfId` (or candidate name) into a full filing
summary.

Findings from live exploration of the OCPF API that constrain the design:

- `filer/payload/{cpfId}` returns everything the command needs in **one call**:
  - `filer` — the full profile (mirrors `filer/{cpfId}`): `cpfId`, `isActive`,
    `accountType` (with `isLegislative`, `isCandidate`, etc.), `fullNameReverse`,
    `committeeName`, `partyAffiliation`, `officeSoughtDescription`, `officeHeld`,
    `organizationDate`, `closedDate`, `candidate.treasurer`/`treasurer`,
    `bankName`.
  - `ytdReport` — the cumulative YTD record: `receiptsYtd(+Numeric)`,
    `expendituresYtd(+Numeric)`, `currentCashOnHand(+Numeric)`,
    `bankReportEndDate` — the same shape the `race` table renders.
  - `logReports` — a short list of the most recent reports: `reportId`,
    `reportTypeDescription`, `reportingPeriod`, `dateFiledHeader`,
    `receiptTotal`, `expenditureTotal`, and a `reportLink` to ocpf.us.
- The free-text filer name-search endpoints (`filers/listings/...`,
  `filers/options/...`, `public/search/...`) are dead (404). There is no live
  way to resolve an arbitrary name to a `cpfId`. The only working name→cpfId
  path we already trust is the legislative YTD field (`filerName` + `cpfId`),
  which the `race` command already fetches and merges.
- A raw `cpfId` works with `filer/payload/{cpfId}` for **any** filer type
  (candidate, PAC, statewide, ballot question), not just legislative.

## Goals / Non-Goals

**Goals:**
- One command, `ocpf filer <filer> [--year]`, that answers "what has this
  candidate filed and what are their finances?" in a single API call once the
  `cpfId` is known.
- Accept a raw `cpfId` (universal) or a candidate name (legislative-only,
  reusing the `race` field), with no-guess ambiguity handling identical in
  spirit to district resolution.
- Reuse `cli-foundation` and the `race` merge machinery rather than duplicating
  HTTP, rendering, or feed logic.
- Honest presentation: cumulative YTD money plus the as-of report date; no money
  segmentation by election.

**Non-Goals:**
- Line-item drill-down (donors, individual expenditures) — a later `report`
  command.
- Name resolution for non-legislative filer types (reachable by cpfId in v1).
- Audit/correspondence documents and full paginated report history.

## Decisions

### Argument resolution: cpfId-or-name, name is legislative-only
`filer(<filer>)` first checks whether the argument is a bare integer. If so, it
is treated as a `cpfId` and passed straight to `filer/payload/{cpfId}` (works
for any filer type). Otherwise it is treated as a name: fetch the merged
legislative field for `--year` (the exact `fetch_merged_field` the `race`
command uses) and match case-insensitively against each row's `filerName`.
Exactly one match → use its `cpfId`; zero → error; more than one → print the
candidates (`cpfId`, name, office) and exit without guessing.

*Rationale:* the API offers no general name search, so honest name lookup must
piggyback on a feed we already trust. Scoping name lookup to legislative filers
matches the project's v1 scope while keeping cpfId lookup universal.
*Alternatives:* bundling OCPF's bulk `candidates.txt` for name search (rejected —
the project reads live from the API, no bundled dataset); requiring a `cpfId`
only (rejected — users get cpfIds from `race`, but name lookup is a small, safe
convenience on top of the same data).

### Single-call fetch
Use `filer/payload/{cpfId}` alone for profile + YTD + recent log, rather than
stitching `filer/{cpfId}` + `reports/baseReportTypes/{cpfId}` +
`reports/reportList/{cpfId}`. One request, fewer failure modes.
*Trade-off:* the recent log is only the handful of reports the payload returns;
full history is deferred to a future `report`/`reports` command.

### Shared merge helpers
`fetch_merged_field` / `_reports_of` currently live in `commands/race.py`. Name
resolution needs them too. Factor the feed-merge helpers into a small shared
module (e.g. `legislative.py`) that both `race` and `filer` import, or import
them from `race` if that stays clean. Either way, no behavior change to `race`.

### Output contract
Default (human): a profile header block (committee/candidate, party, office,
status, organized/closed dates, treasurer), a YTD line (raised / spent / cash on
hand, formatted currency, with the as-of `bankReportEndDate`), and a recent-reports
table (Type, Period, Filed, Receipts, Expenditures). `--json`: emit the relevant
payload records (`filer`, `ytdReport`, `logReports`) including numeric values.
Human status goes to stderr; a missing/unknown `cpfId` is a clear error with a
non-zero exit.

## Risks / Trade-offs

- **Name lookup misses non-legislative filers** → By design in v1. Mitigation:
  the error message for a no-match name tells the user they can pass a `cpfId`
  directly (which works for any filer). cpfIds are discoverable via `ocpf race`.
- **Payload shape drift** (OCPF renames a payload key) → Read defensively with
  `.get(...)`, render what is present, and never crash on a missing optional
  field; surface hard failures as `OcpfApiError` with a non-zero exit.
- **`logReports` is not full history** → Documented as "recent reports"; header
  wording avoids implying completeness. Full history is a later command.
- **Unknown/closed cpfId** → `filer/payload/{cpfId}` for a bad id may 404 or
  return an empty/inactive filer; map the former to `OcpfApiError` and the
  latter to a clear "no filer found for cpfId N" message, both non-zero.

## Open Questions

- Whether to expose `--reports N` to widen the recent-report list once a
  paginated history command exists. Default: show what the payload returns.
- Whether to factor the shared feed-merge helpers into `legislative.py` now or
  defer until a third consumer appears — implementer's call during apply.
