## 1. Shared date-option parsing

- [x] 1.1 Move `parse_date_option` out of `commands/expenditures.py` into a
      shared module (alongside the other cross-command helpers), re-importing it
      in `commands/expenditures.py` so its public surface is unchanged; verify by
      updating only the import path in `tests/test_expenditures.py` and
      confirming `uv run pytest tests/test_expenditures.py` passes with no
      assertion changes (a pure move — any other needed edit means behavior
      drifted).

## 2. Summary fetch in the search client

- [x] 2.1 Add `fetch_summary(params)` to `src/ocpf_cli/search.py` sending
      `PageSize=1`, `StartIndex=START_INDEX_BASE` and `withSummary=true`,
      returning the summary dict and the single sample record; verify with a
      mocked response that exactly one request is issued and `StartIndex` is
      never 0.
- [x] 2.2 Raise `OcpfApiError` when the response carries no `summary`; verify a
      mocked summary-less response raises rather than returning zero (spec:
      "Summary missing from the response").
- [x] 2.3 Add the window guard: given the requested start and end, raise
      `OcpfApiError` when the sample record's date falls outside them; verify
      with a mocked response whose record predates the window that the call
      raises, and with an in-window record that it does not (design Decision 2).
- [x] 2.4 Add `fetch_category_total(cpf_id, category, start, end)` wrapping the
      above with the `CATEGORY_*` constants, reusing `_looks_like_receipt` to
      reject receipt-shaped records when expenditures were requested; verify a
      mocked receipt-shaped response raises for an expenditure query (spec:
      "Money received is never reported as money paid").

## 3. `ocpf totals` command

- [x] 3.1 Add `src/ocpf_cli/commands/totals.py` with a `totals` command taking
      `<filer>`, required `--start`/`--end`, and a Typer enum `--category`
      defaulting to receipts; register it in `cli.py`; verify
      `uv run ocpf totals --help` lists it and that `--category bogus` is
      rejected by Typer before any request is issued.
- [x] 3.2 Resolve the filer via `resolve.resolve_filer` with a `--resolve-year`
      escape hatch, reporting ambiguity and no-match as the other filer-scoped
      commands do; verify ambiguous and unmatched names exit non-zero with the
      candidate list.
- [x] 3.3 Reject a missing bound, an unparseable date, and an inverted window
      before issuing any request; verify each exits non-zero with a message
      naming the problem, and that no HTTP call is made (spec: "Both bounds are
      required").
- [x] 3.4 Render the count, the total as currency, the category label and the
      window; verify against the live API that
      `uv run ocpf totals 14902 --start 2024-01-01 --end 2024-10-31` reports
      1,277 records totalling $401,190.59 and names the window, and that
      `--start 2024-01-01 --end 2024-12-31` reports 1,646 and $560,090.46.
- [x] 3.5 Verify the expenditures category against the live API:
      `uv run ocpf totals 14902 --start 2023-11-01 --end 2024-10-25 --category
      expenditures` reports 845 records totalling $397,182.30, and the same
      window as receipts reports 1,760 and $581,434.45.
- [x] 3.6 Report an empty window as `$0.00` over 0 records on stdout with exit
      zero; verify with a window in which the filer has no records that the exit
      code is 0 and the window is named (spec: "Window containing no records").
- [x] 3.7 Add `--json` emitting cpfId, category, window, count and numeric total
      and no human output; verify the document parses and carries both bounds.

## 4. Documentation

- [x] 4.1 Record in `CLAUDE.md`'s `search/items` section that `StartDate`/
      `EndDate` are real, inclusive, `M/D/YYYY`, compose with `CpfId`, work
      across year boundaries and back to 2010, and that `withSummary=true` with
      `PageSize=1` answers a scalar question in one request; verify by re-running
      the call cited in the note.
- [x] 4.2 Document `ocpf totals` in `README.md`, leading with why a windowed
      total differs from the published year-to-date figure (the 2020 and 2024
      figures for cpfId 14902); verify the README commands run as written.
- [x] 4.3 Add a CHANGELOG entry under an unreleased heading; verify it follows
      the format of the `ocpf expenditures` entry.
- [x] 4.4 Run `uv run pytest` and confirm the suite passes with the new tests and
      that no existing test required changes beyond the import move in 1.1.
