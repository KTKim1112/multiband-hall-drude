# Tasks — in what order, and what must hold before moving on

Feature 001 · 2026-08-26

Every task names the requirements it discharges. No phase begins before the
previous gate holds. Gates are not advisory: "it seems to work, let us move
on" repeats until nobody can find where it went wrong.

---

## Phase 1 — The physics core

Nothing here reads a file, parses an argument or draws anything.

| Task | Work | Requirements |
| --- | --- | --- |
| T101 | `core/errors.py` — one exception type carrying a stable code and a machine-readable detail mapping | Article IV |
| T102 | `core/constants.py` — the elementary charge, and nothing else | research 1 |
| T103 | `core/units.py` — every boundary/SI conversion, and its test in both directions | NR-004, Article V |
| T104 | `core/drude.py` — conductivity tensor, resistivity inversion, conductivity from measured resistivity, field polarity | PM-001, PM-002, NR-001 |
| T105 | `tests/test_drude_known.py` — K1 to K8 of research 2.3, each to its measured tolerance | PM-001, PM-002 |
| T106 | `core/canonical.py` — order by decreasing mobility within each sign; report an order change | PM-003, FR-047 |
| T107 | `core/metrics.py` — coefficient of determination, RMSE, robust channel scale with its documented fallbacks, runs-test score | FR-020, FR-040, AC-007 |
| T108 | `tests/test_core_purity.py` — parse the imports of every module under `core/`, fail on anything but `numpy` and the standard library | Article I |
| T109 | `tests/test_ascii.py` — fail on non-ASCII outside `messages.py` and `cli.py` | Article IV, Article VIII |

> **Gate 1** — `pytest` green. K1 to K8 in particular, since every later number
> rests on them. `test_core_purity.py` and `test_ascii.py` must be failing for
> the right reason before they pass: each is checked once against a deliberate
> violation, then the violation is removed.

---

## Phase 2 — Configuration and data intake

| Task | Work | Requirements |
| --- | --- | --- |
| T201 | `config.py` — the schema of `data-model.md` section 2, with every default filled in, producing `ResolvedConfig` | FR-003, FR-011, FR-013, FR-016, FR-018, FR-019, FR-021, FR-022, FR-026, FR-027, FR-028, FR-029, FR-030, FR-032, FR-033, FR-034, FR-035, AC-001, AC-002, AC-003, AC-004, AC-005, AC-006, AC-007 |
| T202 | Validation — every `E_CONFIG_*` code, unknown fields rejected rather than ignored | FR-012, FR-014, FR-015, FR-017 |
| T203 | `messages.py` — Korean wording keyed by code, for every code in `data-model.md` section 3 | Article IV, Article VIII |
| T204 | `dataio.py` — read the table, map the four columns, drop unusable records and count them, group by temperature, check each group against the free-parameter count | FR-001, FR-002, FR-004, FR-005, FR-006 |
| T205 | Preprocessing — Hall scale factor, symmetrisation, antisymmetrisation, mirror interpolation with counts of interpolated and absent | FR-007, FR-008, FR-009, FR-010 |
| T206 | `tests/test_config.py` and `tests/test_dataio.py` — one test per error code, asserting on the code and never on the wording | Article IV |

> **Gate 2** — every `E_CONFIG_*` and `E_DATA_*` code in `data-model.md`
> section 3 is raised by at least one test, and every code raised by the source
> appears in `data-model.md`. Checked by a test that compares the two lists.

---

## Phase 3 — The objective, and the round trip

| Task | Work | Requirements |
| --- | --- | --- |
| T301 | `fitting.py` — packing carriers into the log parameter vector and back, bounds in log space, exact bound values on output | NR-001, NR-002, NR-006 |
| T302 | `core/residual.py` — admission of records by field window, channel selection, space selection, robust normalisation, channel weights, low-field emphasis | FR-018, FR-019, FR-020, FR-021, FR-022, FR-049 |
| T302b | The field window excludes records from the comparison only. Prediction, output and residuals still cover every record, and fit quality is computed inside and outside separately | FR-050, FR-051 |
| T303 | Single-temperature solve with multistart: seeded, every start retained, the best kept, the seed recorded | FR-033, FR-034, FR-035, FR-036, NR-005, Article VII |
| T304 | `tests/test_roundtrip.py` — generate data from known parameters, recover them | **AC-008** |

> **Gate 3 — the decisive one.** `test_roundtrip.py` recovers the generating
> parameters of a single-carrier data set to `1e-6` relative, and of a
> two-carrier data set to the tolerance research 4.2 measured. Nothing in
> Phases 4 to 7 is begun before this passes, because a factor of two, a flipped
> sign or a lost unit conversion is invisible in every other test.

---

## Phase 4 — Temperature strategies and coupling

| Task | Work | Requirements |
| --- | --- | --- |
| T401 | Independent strategy | FR-023 |
| T402 | Sequential strategy — the result at one temperature seeds the next | FR-024 |
| T403 | Global strategy — all temperatures as one problem; record which strategy ran | FR-025, FR-026 |
| T404 | `core/penalties.py` — coupling on `log p`, first and second order, per-carrier inclusion, correct for uneven spacing | FR-027, FR-028, FR-029, FR-030, FR-031, NR-003 |
| T405 | Monotonic penalty, soft, per carrier and quantity | FR-032 |
| T405b | Both penalties act on canonically ordered carriers, and are cut at declared breaks so that no term spans one | FR-052, FR-053 |
| T405c | Reject a coupling or monotonic penalty requested without the global strategy, with `E_CONFIG_COUPLING_WITHOUT_GLOBAL`. Sequential seeds and does nothing else | FR-024, FR-025 |
| T406 | Tests: sequential seeding observable; an isolated excursion suppressed by coupling of either order; a parameter whose logarithm is linear in temperature preserved by second order and flattened by first, which is the case that separates them; and, for FR-031, **one series carrying both spacings** — 2 K below 20 K and 20 K above — where a parameter of constant curvature in `log p` against `T` must produce equal penalty terms in both regions. Replacing one uniform series by another uniform series does not test this and would have passed the formula research 5.5 corrected | FR-024, FR-029, FR-031 |

> **Gate 4** — `pytest` green, and Gate 3 still green with every strategy
> selected in turn. **The test that separates the two coupling orders must
> fail with `order = 1` and pass with `order = 2`**, or it is not testing what
> it claims.
>
> **Corrected 2026-08-26.** That requirement was written against the
> spike-suppression test of T406, which does not discriminate: a first-order
> penalty suppresses an isolated excursion just as a second-order one does,
> so the test passes under both and proves nothing about the distinction.
> What separates them is a *trend*. Research 5.5 says second order allows a
> monotonic or smooth trend to pass unflattened while first order penalises
> the trend itself, so the discriminating case is a parameter whose logarithm
> is linear in temperature: the second-order penalty is then exactly zero at
> the truth, and the first-order one is not. Both tests are kept, and only
> the second carries the gate.

---

## Phase 5 — Diagnostics

| Task | Work | Requirements |
| --- | --- | --- |
| T501 | `D_R2_BELOW`, `D_AT_BOUND` | FR-042, FR-043, AC-001, AC-002, AC-003 |
| T502 | `D_JUMP` and `D_LABEL_SWAP`, evaluated together so a relabelling is not reported as a physical jump | FR-044, FR-047, AC-004 |
| T503 | `D_NON_UNIQUE` — compare retained starts after canonicalisation only | FR-045, AC-005, AC-006 |
| T504 | `D_RESIDUAL_STRUCTURE` | FR-046, AC-007 |
| T505 | `D_LOW_MU_B`, `D_MIRROR_ABSENT`, `D_RECORDS_DROPPED` | FR-005, FR-010 |
| T505b | `D_FIELD_RANGE_ACTIVE`, `D_EXCLUDED_MISMATCH` | FR-049, FR-050, FR-051, AC-009 |
| T506 | Every diagnostic carries what was measured, the threshold, and which acceptance criterion the threshold came from | FR-048 |
| T507 | `D_ILL_CONDITIONED` from the singular values of the converged residual derivative. Calibrated against the four cases of research 4.6 | FR-055, AC-010 |
| T508 | `D_BOUND_OVERRIDE`, and per-temperature bound overrides in `config.py` | FR-054 |
| T509 | `D_PRIORS_ACTIVE` and `D_PRIORS_DISABLED`. One entry per soft prior in force, with strength and scope | FR-056, FR-057 |

> **Gate 5 conditioning check** — `D_ILL_CONDITIONED` reproduces research 4.6:
> the value it records for the reference data set, `4.0e2` on the 14 T synthetic case,
> `5.2e3` on the 3 T one, and `3.6e9` for two same-sign carriers given
> mobilities of 6000 and 6100. The first two must pass AC-010 and the last two
> must fail it, since those are the cases whose parameter accuracy is known.
>
> **Gate 5 addendum** — the field window is a capability, not a setting this
> project uses: research 6 entry C7 measured it and decided against applying
> it to the reference data set. The test therefore asserts the measurement
> that produced that decision. Fitting the reference data with the window
> closed at 6 T raises `D_FIELD_RANGE_ACTIVE` and `D_EXCLUDED_MISMATCH`,
> returns parameters differing from the full-range ones by the amounts C7
> records, and predicts the 6 to 9 T region it did not see with `R2 = 0.757`
> against `0.959` for the full-range fit. A capability whose cost is asserted
> in a test cannot be enabled by accident.
>
> **Gate 5** — every `D_*` code is triggered by at least one test built from
> data constructed to trigger it, and the 2e+2h case of research 4.3 at 3 T
> raises `D_LOW_MU_B` on both low-mobility carriers while raising no
> `D_NON_UNIQUE`. That combination is the measurement this project exists to
> report, so it is asserted directly.

---

## Phase 6 — Output and command line

| Task | Work | Requirements |
| --- | --- | --- |
| T601 | Per-temperature table, parameter table in both declared and canonical order, metric table, singular values and condition number | FR-038, FR-039, FR-040, FR-055 |
| T602 | Figures per temperature per channel, and parameters against temperature | FR-041 |
| T603 | `diagnostics.csv`, and one file per temperature holding every retained start | FR-036, FR-042 |
| T604 | `resolved_config.json`, complete, including the seed, and reproducing the run when fed back in | FR-037, NR-005 |
| T605 | `cli.py` — the only place a sentence appears, in Korean, keyed by code. Carries `--no-priors`, which overrides the declared soft priors and is recorded as having done so | Article IV, Article VIII, FR-057 |
| T606 | `tests/test_cli.py` — end to end on `example_input.csv`; then feed `resolved_config.json` back and require identical numbers | NR-005 |

> **Gate 6** — a run on `example_input.csv` writes every file listed in
> `data-model.md` section 4, and re-running from the emitted
> `resolved_config.json` reproduces every number exactly. A run made with
> `--no-priors` reproduces from its own emitted configuration **without** the
> switch, which is the test that FR-037 records what was in force rather than
> what was declared.

---

## Phase 7 — Agreement with the answer key, example, documentation

| Task | Work | Requirements |
| --- | --- | --- |
| T701 | Example configurations: a two-carrier one for `example_input.csv`, and a two-hole two-electron one for the reference data set of research 2.4 | quickstart |
| T702 | `tests/test_legacy_agreement.py` — `rho_xx` to `1e-12`, `rho_xy` to `1e-12` after negation | plan 4 |
| T703 | `quickstart.md` — verified by running it | |
| T704 | `docs/` — the Korean walkthrough, exempt from Article VIII | Article VIII |
| T705 | `tests/test_reference_fit.py` — **K9**. Fit the reference data set of research 2.4 under PM-001 with two holes and two electrons, and require the global optimum recorded there, every carrier to 1 % after canonicalisation, from every starting point | PM-001, PM-003, FR-045, FR-046 |
| T706 | Prepare the reference data set for intake: the supplied file carries no temperature column, so a derived table with one is written under `tests/data/`, with the transformation recorded | FR-001, FR-002 |

> **Gate 7** — `test_legacy_agreement.py` passes, confirming the correction of
> research 2.1 is the only change of numerical consequence between the
> prototype and the new code. `test_reference_fit.py` passes, and reports
> `D_RESIDUAL_STRUCTURE` on both channels of the reference data set while
> reporting no `D_NON_UNIQUE` — the two diagnostics that research 4.5 measured
> as present and absent respectively.

---

## Requirement coverage

Checked mechanically, not by reading: `tests/test_traceability.py` extracts
every `FR-`, `NR-`, `PM-` and `AC-` identifier defined in `spec.md` and fails
if any is absent from this file. That test is written in Phase 1 and is the
first thing to break when a requirement is added without a task.
