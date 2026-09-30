# Tasks 003 — in what order, and what must hold before moving on

Feature 003 · 2026-09-12

The measurements are in `research.md`; these phases turn them into behaviour a
reader gets without running the experiment themselves.

---

## Phase 11 — The extension and its transform

| Task | Work | Requirements |
| --- | --- | --- |
| T1101 | `core/lorentzian.py` — the model, the closed-form transform, and `sigma_xx(0)` from a low-field window. Pure: Article I allows the core one array library and the standard library, and a constrained solver is neither, so the fit lives outside | FR-067, FR-068, FR-070, NR-009 |
| T1102 | The constrained parameterisation: hole and electron weight per term, and the residual in those variables | NR-011 |
| T1103 | `core/separation.py` — the four identities, and a parity-aware measure of how much of a part came out with the wrong sign | FR-071, AC-023, AC-024 |
| T1104 | `tests/test_lorentzian.py` — the closed forms against split-range quadrature, and the extension against the model of feature 001 | FR-070, NR-009 |
| T1105 | `tests/test_separation.py` — the identities to machine precision, and the wrong-sign measure on both parities | FR-071, AC-023 |

> **Gate 11.** The closed-form transform agrees with quadrature to `1e-6`
> relative at three mobilities, and the separation identities hold to `1e-12`
> against a known mixture. Both are the algebra everything downstream rests
> on, so both are checked before anything is built on them.

---

## Phase 12 — The inversion, per carrier type

| Task | Work | Requirements |
| --- | --- | --- |
| T1201 | `core/spectrum.py` — positive grid, kernel, penalty, peaks, plateaus. The signed grid is removed: after separation there is nothing for it to do, and keeping it would invite the ambiguous formulation back | FR-072, AC-017, AC-019, AC-020 |
| T1202 | Peak weights partition the grid at the valleys, so nothing is discarded. Research 003 section 4.1 records the `14` to `24 %` density bias the half-height region caused | FR-074 |
| T1203 | `spectrum.py` — the five steps, with the extension's weights solved rather than guessed at each start | FR-067, FR-068, FR-070, FR-071, FR-072, FR-073, FR-074 |
| T1204 | Diagnostics `D_SPECTRUM_EXTENSION_UNDERFIT`, `D_SPECTRUM_EXTENSION_SATURATED`, `D_SPECTRUM_EXTENSION_MULTIMODAL`, `D_SPECTRUM_UNCONSTRAINED`, `D_SPECTRUM_NEGATIVE_PART`, `D_SPECTRUM_NOISE_UNREACHED`, `D_SPECTRUM_UNRESOLVED`, `D_SPECTRUM_AMBIGUOUS`, with Korean wording | FR-069, FR-071, FR-073, NR-011, AC-024, AC-021 |
| T1204b | `tests/test_spectrum_diagnostics.py` — each of the eight raised from data built to carry its condition, and the reference sweep pinned to the one code it actually raises | FR-068, FR-069, FR-071, FR-073, NR-011, AC-018, AC-020, AC-021, AC-024 |
| T1205 | `report.py` — the spectrum, its peaks, its stability and its extension, one file each per temperature, and the section into the emitted configuration | FR-068, FR-073, FR-074, FR-077 |

> **Gate 12 — AC-022, the round trip.** Synthetic data from a known
> three-hole three-electron set returns three peaks per branch, every mobility
> within 5 % and every density within 5 %, at the noise this project's sweeps
> actually carry. And the count must not move with the regularisation: one
> plateau per branch across the whole range, which is the defect that caused
> the rewrite.

---

## Phase 13 — What limits the claim

| Task | Work | Requirements |
| --- | --- | --- |
| T1301 | Gate A — walk the slowest carrier's `mu B` down and record where the recovery fails | FR-072, NR-010 |
| T1302 | Gate C — the extension order end to end, and the constrained form against the free one at two start counts | FR-069, NR-011 |
| T1303 | Gate D — seed a larger carrier count from the proposal and report whether the result is determined | FR-075, FR-076 |
| T1304 | The report sentences, on every spectrum: a peak is a conduction channel, the peaks sit where the extension put them, and the count is still the reader's. `tests/test_spectrum_notice.py` pins what they must say and checks they appear only when a spectrum does | FR-076, FR-077 |
| T1307 | The round trip: the spectrum's carriers back through PM-001, per channel, with `D_SPECTRUM_ROUNDTRIP`, `spectrum_roundtrip_<T>K.csv` and Korean wording | FR-079, AC-025 |
| T1308 | `tests/test_spectrum_roundtrip.py` — it passes on a synthetic sweep the model describes and fails on one it does not, and the two are separated by structure rather than by residual size | FR-079, AC-025 |
| T1305b | `tests/test_spectrum_composition.py` — the ladder test passes on generated harmonics and clears the peaks the spectrum returns from them; and an all-hole system returns no electron | FR-078, AC-019 |
| T1305 | Korean twins of `spec.md`, `research.md` and `data-model.md`; identifier parity enforced | Article VIII |
| T1306 | `docs/walkthrough.ko.md` — when to run a spectrum, what the extension order does, and what to do when the extension cannot reach the noise | Article VIII |

> **Gate 13.** Every requirement of `spec.md` 003 appears here; numbering
> across all three features has no gaps; each Korean twin names the same
> identifiers as its source; and the real sweeps run end to end with the
> extension residual, the start agreement and the wrong-sign fraction all
> reported, whatever they turn out to be.

---

## Requirement coverage

FR-067, FR-068, FR-069, FR-070, FR-071, FR-072, FR-073, FR-074, FR-075,
FR-076, FR-077, FR-078, FR-079, NR-009, NR-010, NR-011,
AC-017, AC-018, AC-019, AC-020, AC-021, AC-022, AC-023, AC-024, AC-025.

PM-001, PM-002 and PM-003 are carried over unchanged. FR-063 of feature 002 is
cited rather than restated, and FR-078 restricts where it may be applied.
