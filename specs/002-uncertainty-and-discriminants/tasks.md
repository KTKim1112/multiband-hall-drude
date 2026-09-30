# Tasks 002 — in what order, and what must hold before moving on

Feature 002 · 2026-09-12

Every task names the requirements it discharges. No phase begins before the
previous gate holds. The measurement work is already done and recorded in
`research.md`; these phases turn it into behaviour a reader gets without
having to run an experiment themselves.

---

## Phase 8 — The discriminants that need no resampling

Cheap, independent of everything else, and each removes a candidate
explanation from research 001 Q4.

| Task | Work | Requirements |
| --- | --- | --- |
| T801 | `core/harmonics.py` — test a mobility set against the ladder of research 002 section 4: integer ratios within AC-014, monotonically falling weights, single sign. Pure, `numpy` only | FR-063, AC-014 |
| T802 | `tests/test_harmonics.py` — a synthetic ladder is recognised; the 5, 20 and 40 K carriers are not; a mixed-sign ladder is rejected on the sign condition alone | FR-063 |
| T803 | `core/parity.py` — parity violation of each channel, measured on the raw sweep before symmetrisation | FR-065, AC-015 |
| T804 | `dataio.py` — carry the parity measurement through intake, and record when one polarity only was supplied | FR-065, FR-066 |
| T805 | Diagnostics `D_HARMONIC_LADDER`, `D_PARITY_VIOLATION`, `D_SINGLE_POLARITY`, with Korean wording | FR-063, FR-065, FR-066 |
| T806 | The effective-mobility statement, emitted on every run | FR-064 |

> **Gate 8** — `pytest` green, and three specific results reproduced from
> `research.md`: a synthetic single-orbit ladder is reported as a ladder; the
> real carriers at all three temperatures are reported as **not** a ladder,
> failing the sign condition; and the parity violation of the supplied sweeps
> reads zero, because they arrive symmetrised. The last is a weak test on its
> own, so `D_PARITY_VIOLATION` must also be raised by a sweep with a
> deliberate longitudinal admixture.

---

## Phase 9 — The resampling interval

| Task | Work | Requirements |
| --- | --- | --- |
| T901 | `core/resample.py` — circular block resampling of a field-ordered residual, block length declared. Pure, `numpy` only | FR-059, AC-012 |
| T902 | `tests/test_resample.py` — block length 1 reproduces an independent resample; a block length equal to the record count is a rotation, not the identity; every record appears with the right frequency in expectation | FR-059 |
| T903 | `uncertainty.py` — rebuild, refit and collect, from the converged parameters as the starting point | FR-058, AC-011 |
| T904 | Intervals at the declared fraction, and the correlation matrix | FR-058, FR-062, AC-013 |
| T905 | Derived quantities — total density of each sign, their ratio, their difference — each with its own interval | FR-061 |
| T906 | Pair the interval with the residual-structure diagnostic; raise `D_INTERVAL_LOWER_BOUND` and state the lower-bound reading where it fires | FR-060 |
| T907 | `report.py` — `uncertainty_<T>K.csv`, `correlation_<T>K.csv`, `derived_vs_T.csv`; the block length and resample count into `resolved_config.json` | FR-058, FR-059, FR-061, FR-062 |

> **Gate 9 — the decisive one, and it is a coverage test.** AC-016: on data
> built from known parameters plus **independent** noise, the interval covers
> the generating value at approximately the declared rate. Measured over at
> least 100 synthetic data sets, for every parameter. An interval that does
> not cover is not an interval, and no amount of correct plumbing substitutes
> for this.
>
> **Gate 9 addendum** — the three numbers of `research.md` section 3 are
> reproduced by test: block length 1 gives a largest one-sigma near `4 %`,
> block length 20 near `14 %`, and the strongest correlation is `h_fast.n`
> with `e_fast.n` above `+0.85` at every block length tried.

---

## Phase 10 — What the numbers mean, written down

| Task | Work | Requirements |
| --- | --- | --- |
| T1001 | The hole excess of research 001 section 2.4 restated with its interval, and the Gate 7 test amended to assert on both | FR-061 |
| T1002 | `NR-007` recorded as the reason `fit_space` keeps its default, with the measurement, and a test that fitting in the other space is available and worse on this data | NR-007 |
| T1003 | `NR-008` — a test that a resample with the parity of its channel enforced gives the same parameters as one without | NR-008 |
| T1004 | Korean twins of `spec.md` and `research.md`; identifier parity enforced | Article VIII |
| T1005 | `docs/walkthrough.ko.md` — how to read an interval that is a lower bound, and what the correlation matrix is for | Article VIII |

> **Gate 10** — every requirement of `spec.md` 002 appears in this document;
> requirement numbering across features 001 and 002 together has no gaps; each
> Korean twin names the same identifiers as its English source. The reference
> run reports a hole excess with an interval, and the walkthrough tells a
> reader what to do when the residual-structure diagnostic accompanies it.

---

## Requirement coverage

FR-058, FR-059, FR-060, FR-061, FR-062, FR-063, FR-064, FR-065, FR-066,
NR-007, NR-008, AC-011, AC-012, AC-013, AC-014, AC-015, AC-016.

PM-001, PM-002 and PM-003 are carried over from feature 001 unchanged and are
discharged by its tests; research 002 section 5.1 records a rejected proposal
to invert PM-001.
