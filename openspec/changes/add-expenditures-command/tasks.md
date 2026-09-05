## 1. Extract shared filer resolution

- [x] 1.1 Move `FilerMatch`, `FilerResolutionError`, `_normalize`, and
      `resolve_filer` from `commands/filer.py` into a new
      `src/ocpf_cli/resolve.py`, re-importing them in `commands/filer.py` so its
      public surface is unchanged; verify by updating only the import path in
      `tests/test_filer.py` and confirming `uv run pytest tests/test_filer.py`
      passes with no assertion changes (a pure move — any needed test edit
      beyond imports means behavior drifted).
- [x] 1.2 Confirm `uv run ocpf filer "Uyterhoeven" --year 2026` still prints the
      same profile as before the move, and commit the move on its own so a
      regression in it is bisectable separately from the new command.

## 2. `search/items` client

- [x] 2.1 Add `src/ocpf_cli/search.py` with `CATEGORY_EXPENDITURES = "B"` as a
      module constant plus a comment citing
      `https://api.ocpf.us/swagger/v1/swagger.json` and the silent-fallback
      hazard (unrecognized `SearchTypeCategory` returns receipts); verify the
      constant is never built from CLI input by grepping that no caller passes a
      user value into that parameter.
- [x] 2.2 Implement `fetch_items(params)` that pages on `StartIndex`/`PageSize`
      with `withSummary=true`, accumulating until the record count reaches
      `summary.count`; verify with a respx-mocked three-page response that all
      records are returned and only the expected number of requests are made.
- [x] 2.3 Raise `OcpfApiError` when the accumulated count falls short of
      `summary.count`, and break out with an error when a page returns zero new
      items; verify with a mocked short/stalled response that each case raises
      rather than returning a partial set (spec: "Retrieval is incomplete").
- [x] 2.4 Add a record-shape assertion that rejects receipt-shaped items
      (`contributorCpfId`/`fullNameReverse` present, `vendor` absent) with a
      clear `OcpfApiError`; verify with a mocked response containing receipt
      records that the call raises (spec: "Expenditures are not confused with
      receipts").
- [x] 2.5 Attach a numeric amount to each record via `render.parse_currency` and
      a parsed date from the `M/D/YYYY` string; verify unit tests cover
      `"$1,234.56"`, `"$0.00"`, and a malformed value.

## 3. Filtering and aggregation

- [x] 3.1 Implement local filters for `--year`, `--since`, `--until`,
      `--vendor` (case-insensitive substring over the payee, including
      `clarifiedName` when present), `--min-amount`, and `--max-amount`,
      combining conjunctively; verify each filter and one combination against a
      fixture record set (spec: "Filtering expenditures").
- [x] 3.2 Implement `group_by_vendor` returning payee, total, and count ordered
      by total descending, grouping on the effective payee — OCPF's
      `clarifiedName` where supplied, the filed string otherwise (design
      Decision 6, revised during implementation); verify with a fixture that
      variants OCPF clarified collapse into one row carrying every filed
      spelling in `filedAs`, that two similar-looking *unclarified* strings stay
      two rows, and that the grouped totals sum to the itemized total.

## 4. Command and rendering

- [x] 4.1 Add `src/ocpf_cli/commands/expenditures.py` with the Typer signature
      from the proposal and register it in `cli.py`; verify
      `uv run ocpf --help` lists `expenditures` and `uv run ocpf expenditures
      --help` shows every flag.
- [x] 4.2 Render the itemized view (date, amount, vendor, purpose, record type)
      with a trailing total and record count, marking bank-reported records
      distinguishably; verify against cpfId 17436 that
      `OUTGOING WIRE TRANSFER` rows are visibly marked as bank-reported
      (spec: "Record provenance and payee fidelity").
- [x] 4.3 Render the `--by-vendor` view; verify `uv run ocpf expenditures
      Uyterhoeven --year 2026 --by-vendor` shows `EAST COAST PRI` at
      $66,034.34 atop the list and that the rollup total matches the itemized
      total for the same query.
- [x] 4.4 Implement `--limit` so it caps displayed rows, notes the truncation,
      and leaves the reported total describing the full filtered set; verify a
      test asserts the total is unchanged by the limit.
- [x] 4.5 Implement `--json` for both views, emitting numeric amounts alongside
      display strings and a per-record `reportId`/source link, with no
      human-formatted output; verify piping to `python -m json.tool` succeeds
      for the itemized, `--by-vendor`, and empty-result cases.

## 5. Exit-code contract

- [x] 5.1 Make a filter that matches nothing print a no-match line naming the
      filter plus the searched record count and date span, and exit zero; verify
      `uv run ocpf expenditures Uyterhoeven --vendor "Connection Strategies";
      echo $?` prints `0` (spec: "Empty filtered result is a successful
      finding").
- [x] 5.2 Keep unresolvable filer, API error, and a filer with zero expenditure
      records exiting non-zero; verify tests assert exit 1 for an ambiguous
      name, an unknown cpfId, and a raised `OcpfApiError`.
- [x] 5.3 Audit `race` and `filer` for any existing test asserting non-zero on an
      empty *filtered* result; verify `uv run pytest` passes whole and reconcile
      any such assertion with the revised `cli-foundation` requirement rather
      than working around it.

## 6. Documentation

- [x] 6.1 Record the `search/items` contract in `CLAUDE.md` under the API
      reference section — the swagger URL, the `B`/`R`/`S`/`D` category codes and
      their silent fallback to receipts, that `Name` filters and `VendorName` is
      inert, and the `{summary, items}` response shape; verify the section names
      each fact a future command would otherwise rediscover by probing.
- [x] 6.2 Add an `ocpf expenditures` section to `README.md` matching the
      existing `race`/`filer` sections, including a worked example and a note
      that the item-search total legitimately differs from the filer's YTD
      figure (design Non-Goals); verify the example output is copied from a real
      run, not hand-written.
- [x] 6.3 Add a `CHANGELOG.md` entry for the new command and the exit-code
      refinement; verify it names the behavior change so a user upgrading sees
      that an empty filtered result now exits zero.

## 7. Verification

- [x] 7.1 Run `uv run pytest` and confirm the full suite passes, including the
      untouched `race` and `filer` tests.
- [x] 7.2 Run `openspec validate add-expenditures-command --strict` and confirm
      it reports no errors.
- [x] 7.3 Reproduce the session that motivated this change end to end: confirm
      `uv run ocpf expenditures Uyterhoeven --vendor "Connection Strategies"`
      and `--vendor "Cohen"` both report no matches and exit zero, and that
      `uv run ocpf expenditures Uyterhoeven --json` returns 1,019 records
      totalling $394,691.07 — the figures established by hand against the live
      API.
