# Data model 003 — what feature 003 adds

> English is normative. `docs/003-data-model.ko.md` is its translation.
>
> Extends the data models of features 001 and 002. Nothing declared there
> changes.

---

## 1. Configuration

```text
spectrum
  enabled                false      opt-in: one inversion per regularisation step
  mu_min_cm2Vs           100        grid and extension bounds, low end
  mu_max_cm2Vs           300000     and high end
  points_per_decade      40         AC-017
  lorentzian_terms       6          the extension order of FR-069
  lorentzian_multi_start 12         starting points for the extension, FR-068
  lorentzian_constrained true       NR-011; false reproduces the published method
  zero_field_window_T    0.5        the window sigma_xx(0) is estimated over, FR-067
  alpha_min              1e-16      regularisation strengths examined, low
  alpha_max              1e-2       and high; one step per decade
  noise_source           "residual" "residual" estimates it from the second
                                    differences of the fit residual; a pair of
                                    numbers declares it directly, per channel
  discrepancy_factor     1.1        AC-018
  peak_floor             0.02       AC-019, as a fraction of the branch maximum
                                    and of the whole spectrum
  plateau_decades        3          AC-020
  roundtrip_tolerance    0.05       AC-025
```

Two settings a reader must think about, and the document says so where each
is declared. `lorentzian_terms` is the order of FR-069, which the program does
not infer: research 003 section 3.3 measured an order below the number of
distinct mobilities failing by a factor of seven. `noise_source` decides what
the discrepancy principle is measured against, and nothing downstream can
recover from getting it wrong.

---

## 2. Diagnostic codes

Nine, and they divide into three groups: what the extension of step 2 did, and
what the inversion of step 5 could settle -- and then one that stands apart,
because it is the only one that compares the result with the measurement
rather than with the method's own expectations. The second group is reported
**per carrier type**, because after separation the hole and the electron
problems succeed and fail independently.

| Code | Raised when | Source |
| --- | --- | --- |
| `D_SPECTRUM_EXTENSION_UNDERFIT` | The Lorentzian residual exceeds ten times the noise: fewer terms than the data has distinct mobilities, and everything downstream inherits the shortfall | FR-069, AC-021 |
| `D_SPECTRUM_EXTENSION_SATURATED` | A term sits on the declared mobility range, so the range and not the data placed it | FR-069 |
| `D_SPECTRUM_EXTENSION_MULTIMODAL` | Fewer than half the starts reached the best solution, so the extension is a choice among several | FR-068 |
| `D_SPECTRUM_UNCONSTRAINED` | The non-negativity of NR-011 was switched off, reproducing the published method and admitting the cancelling-weight basin with it | NR-011 |
| `D_SPECTRUM_NEGATIVE_PART` | A separated conductivity lost its sign somewhere. Impossible under NR-011, so this fires only with the constraint off | FR-071, AC-024 |
| `D_SPECTRUM_NOISE_UNREACHED` | No examined strength fits this carrier type to the declared noise | FR-073, AC-018 |
| `D_SPECTRUM_UNRESOLVED` | This carrier type has no plateau of the declared length | FR-073, AC-020 |
| `D_SPECTRUM_AMBIGUOUS` | This carrier type has more than one plateau, so more than one count fits | FR-073, AC-020 |
| `D_SPECTRUM_ROUNDTRIP` | The carriers read off the spectrum, put back through the model, do not reproduce this channel of the sweep. Raised per channel | FR-079, AC-025 |

None says the spectrum is wrong. They say which part of it a reader may quote.

## 3. Output files

| File | One row per | Carries |
| --- | --- | --- |
| `spectrum_<T>K.csv` | grid point | mobility, then one density column per carrier type |
| `spectrum_peaks_<T>K.csv` | peak | carrier kind, mobility, the density it implies, weight, the strength it came from |
| `spectrum_stability_<T>K.csv` | carrier type and strength | strength, residual norm, the target it is measured against, roughness, peak count |
| `spectrum_extension_<T>K.csv` | Lorentzian term | mobility, hole weight `p`, electron weight `q`, and the raw `a`, `b` |
| `spectrum_roundtrip_<T>K.csv` | channel | the largest relative difference between the measurement and the spectrum's carriers put back through the model, and the tolerance it is judged against |

`resolved_config.json` gains the `spectrum` section including the selected
strength and the noise level used, so FR-037 continues to hold.

---

## 4. Report text

Three sentences, with every spectrum.

- A peak is a channel of the conduction, not a band of the Fermi surface. One
  non-circular orbit read through four cyclotron harmonics was measured in
  research 003 section 7 to return three peaks, so a peak count is an upper
  bound on the number of Fermi surfaces and not an estimate of it.
- Every peak sits on a mobility the extension chose, so the spectrum cannot
  find structure the extension did not admit. FR-077.
- The carrier count remains the reader's declaration; the spectrum proposes.
  FR-076.
