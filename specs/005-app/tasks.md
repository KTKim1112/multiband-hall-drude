# Tasks 005 — the program for a reader who does not run commands

> English is normative. Phases carry gates; a gate is a measurement, not an
> opinion.

---

## Phase 17 — The server

| Task | Work | Requirements |
| --- | --- | --- |
| T1701 | `mbfit/workflow.py` accepts hooks: a progress callback and a stop request asked before every fit, and a stop that keeps finished temperatures | FR-097, FR-098, AC-033 |
| T1702 | `mbfit/uncertainty.py` resampling accepts the same, and keeps nothing when stopped | FR-101 |
| T1703 | `app/tables.py` — header detection, the proposed mapping, temperature from the file name, units converted at one boundary, duplicate temperatures refused | FR-093, FR-094, FR-095, FR-096, AC-034 |
| T1704 | `app/jobs.py` — background jobs with progress, stop, and partial results | FR-097, FR-098, FR-101 |
| T1705 | `app/runner.py` — the preliminary model, the analysis, the precise check, and the same tables and page the command line writes | FR-102, FR-104 |
| T1706 | `app/routes.py`, `app/main.py` — the endpoints of data model 005, codes and never sentences | FR-099, FR-100, FR-105 |
| T1707 | `tests/test_app_tables.py`, `tests/test_app_api.py` — every code, a stop that keeps what finished, downloads equal to the command line's files | FR-093 to FR-105 |

> **Gate 17.** Through the server alone: the twelve reference files uploaded as
> they are, mapped with temperatures taken from their names, analysed in fit
> mode, stopped part way with the finished temperatures kept, and run again to
> the end with tables identical to the command line's for the same data.

---

## Phase 18 — The page

| Task | Work | Requirements |
| --- | --- | --- |
| T1801 | `frontend/` — files, mapping, settings, progress with stop, results | FR-093, FR-094, FR-097, FR-098 |
| T1802 | The mode chosen by the reader with neither preselected, and what each measured shown beside it | FR-099 |
| T1803 | The verdict first, then curves, trends and combinations; precise check per temperature | FR-101, FR-103 |
| T1804 | `frontend/src/labels.ts` — every sentence and every code's message in one place | FR-105 |
| T1806 | Files dropped anywhere on the page; separate channel files, decimal commas, UTF-16 and unit lines read; the page runs the data rule only | FR-096, FR-099 |
| T1805 | The preliminary model named on the page, and a configuration document accepted in its place | FR-102 |

> **Gate 18.** The page builds with no type error, and the built page served by
> the server walks the path of Gate 17 in a browser.

---

## Phase 19 — Delivery

| Task | Work | Requirements |
| --- | --- | --- |
| T1901 | `app/desktop.py` — loopback, a port the system chooses, the browser once the server answers | FR-106 |
| T1902 | `packaging/` — entry script, one-folder build, no compression, a console window, the build script | FR-106 |
| T1903 | `README.md` and `docs/README.ko.md` — how to run the folder, and that the command line is still whole | FR-107 |
| T1904 | Research 005 — the preliminary model measured, the stop delay measured, the build measured | FR-102, AC-033 |
| T1905 | Korean twins of `spec.md`, `data-model.md` and `research.md`; identifier parity enforced | Article VIII |
| T1906 | The address of the previous run reused when free; a page whose server is gone says so and returns by itself | FR-106, FR-108, AC-035 |
| T1907 | `app/runner.py` recount and its route; the results page refits one temperature at a chosen count, beside the verdict and with its price | FR-109, AC-036 |
| T1908 | `workflow.roughness_of` and `workflow.smooth_band`: a band reports how far it is from a smooth series, and the coupling of FR-027 is offered at three strengths with its price per temperature | FR-109, AC-037, AC-038 |
| T1909 | The spectrum carried into the outcome and drawn on the page, folded away, with the window it became | FR-110 |
| T1910 | `frontend/src/text/` — one file per language, `en` typed against `ko` so the build catches a sentence only one of them has; the choice remembered | FR-111, Article VIII |
| T1911 | The report of FR-092 draws the spectrum folded away and reports the roughness of the band it ran; the command line prints the same number | FR-107, FR-109, FR-110 |
| T1912 | The refit reaches the trends, the curves and the carrier table beside the procedure's answer; the drawing is rendered and its marks counted | FR-109 |
| T1913 | The refit and the coupling become separate requests; a stopped coupling leaves the refit standing; both report their temperature and can be stopped | FR-109, AC-033 |
| T1914 | `mbfit/fitting.py` `fit_global`: one starting point for a refinement, a budget checked inside the residual, progress and a stop | FR-109, AC-039, AC-040 |
| T1915 | `workflow.smooth_band` as a setting the procedure applies, so a coupled band is reachable from the command line | FR-107, FR-112 |
| T1916 | The adjustment step: adjustments accumulate per temperature, shown beside the procedure's answer | FR-112 |
| T1917 | Confirming re-runs the procedure under the settings the adjustments amount to and writes its tables, page and document; the download serves them | FR-104, FR-112, NR-013 |
| T1918 | Korean twins of the amended specification and data model; identifier parity enforced | Article VIII |
| T1919 | A pinned refit gets its own budget and starting points instead of the search's, measured from the cost of a six-carrier fit; a count that will not fit is named rather than answered with the count it was overriding | FR-109, AC-041, AC-042 |

> **Gate 19.** The built folder starts from a double-click, opens the page, and
> finishes a fit-mode analysis of one reference file. Whether it runs on a
> machine with no interpreter is answered only by trying it on one, and is
> recorded as not yet answered until then.

---

## Coverage

FR-093, FR-094, FR-095, FR-096, FR-097, FR-098, FR-099, FR-100, FR-101,
FR-102, FR-103, FR-104, FR-105, FR-106, FR-107, FR-108, FR-109, FR-110,
FR-111, FR-112, NR-013, AC-033, AC-034, AC-035, AC-036, AC-037, AC-038,
AC-039, AC-040, AC-041, AC-042.
