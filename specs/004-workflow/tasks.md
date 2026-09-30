# Tasks 004 — the workflow

> English is normative. Phases carry gates; a gate is a measurement, not an
> opinion. The numbers in each gate were recorded before the code that makes
> them pass was written.

---

## Phase 14 — The procedure

| Task | Work | Requirements |
| --- | --- | --- |
| T1401 | `mbfit/workflow.py` — the two modes, and a reader who must choose between them | FR-080, FR-081 |
| T1402 | The mobility window, per carrier type and never per peak | FR-082, AC-030 |
| T1403 | Starting points from the branch distribution, in equal-weight segments | FR-083 |
| T1404 | Every combination up to the bound, fitted and kept | FR-084 |
| T1405 | Four gates, fit quality first and not tradeable; the nearest miss named when none passes | FR-085, FR-086, AC-026, AC-027, AC-028 |
| T1406 | Conditioning as a grade rather than a gate | FR-087, AC-031 |
| T1407 | The wall-clock budget, enforced inside the residual of `fitting.py` | FR-088, NR-012, AC-029 |
| T1408 | Resampling opt in, per temperature | FR-089 |
| T1409 | The count held fixed across a range, and what holding it cost | FR-090 |
| T1410 | `spectrum.fit_extension` accepts a starting point, so the loop of spectrum mode can feed the fit back | FR-080 |
| T1411 | `workflow` configuration section, and `--mode` on the command line | FR-080, FR-081 |
| T1412 | `--symmetrize-rhoxx` and `--antisymmetrize-rhoxy`, off by default | FR-008, FR-009 |

> **Gate 14.** `workflow.analyse` reproduces, in one call, what the procedure
> produced when it was assembled by hand: the 5 K sweep selects `2h+2e` at
> grade `A`, with the condition number, both `R^2` and every fitted parameter
> equal to what research 004 section 2 recorded, and no carrier leaving the
> window the spectrum supplied. The numbers themselves are in that record,
> which is measured from a sample and is not published with the program.

---

## Phase 15 — What limits the claim

| Task | Work | Requirements |
| --- | --- | --- |
| T1501 | `tests/test_workflow.py` — the grade, the window, the seeds, the gates, and the end-to-end round trip | AC-032 |
| T1502 | The two traps pinned by tests that name their measured cost: per-peak windows, peak-list seeds | FR-082, FR-083 |
| T1503 | Constraint ledger C11 to C15, five answers each | Article X |
| T1504 | Korean twins of `spec.md` and `research.md`; identifier parity enforced | Article VIII |
| T1505 | `docs/walkthrough.ko.md` — which mode to run, and what the grade means | Article VIII |

> **Gate 15.** Every requirement of `spec.md` 004 appears here; numbering
> across all four features has no gaps; each Korean twin names the same
> identifiers as its source.

---

## Phase 16 — What the reader receives

| Task | Work | Requirements |
| --- | --- | --- |
| T1601 | `data-model.md` 004 -- the three workflow tables and the report page | FR-091, FR-092 |
| T1602 | `mbfit/workflow_report.py` -- the tables, and the page with every label passed in so the module stays ASCII | FR-091, FR-092 |
| T1603 | `mbfit/cli.py` runs the workflow when `--mode` is given, prints the verdict per temperature, and names the mode with the answer | FR-080, FR-081 |
| T1604 | `tests/test_workflow_report.py` -- the columns, one row per candidate, a page that fetches nothing and names every temperature | FR-091, FR-092 |

| T1605 | Withdraw spectrum mode; the peaks rule of Liu et al., answer the converged fit | FR-080, FR-081 |
| T1606 | `workflow.count` and `--count data|peaks`, the data rule the default | FR-080, FR-081 |
| T1608 | Residual over noise and the runs test on every answer; the count grown past the bound while FR-085 keeps choosing the larger; ledger C17 | FR-082, FR-085, FR-087 |
| T1607 | Research 004 section 4.2: the correction, and the two rules measured on the twelve sweeps; ledger C16 | FR-080 |
| T1609 | Reproducibility taken from the starting points that finished and never from the clock; an unmeasured spread counts as infinite; the candidate tables and the page carry how many starts finished; research 004 section 2 and constraint C15 corrected; ledger C18 | FR-085, FR-088 |
| T1610 | Pinned counts reachable from a configuration document, and over a range; a sweep carrying more carriers than both neighbours share marked and priced, in the tables, the report page, the command line and the page; ledger C19 | FR-090 |

> **Gate 16.** `python -m mbfit --mode fit ...` on the twelve sweeps writes the
> three tables and a page that opens offline and leads with the verdicts.

---

## Requirement coverage

FR-080, FR-081, FR-082, FR-083, FR-084, FR-085, FR-086, FR-087, FR-088,
FR-089, FR-090, FR-091, FR-092, NR-012,
AC-026, AC-027, AC-028, AC-029, AC-030, AC-031, AC-032.

FR-008 and FR-009 of feature 001 are exposed rather than restated: the
symmetrisation already existed and had no way to be switched on from the
command line. PM-001 to PM-003 are carried over unchanged.
