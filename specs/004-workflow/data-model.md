# Data model 004 — what feature 004 adds

> English is normative. `docs/004-data-model.ko.md` is its translation.
>
> Extends the data models of features 001 to 003. Nothing declared there
> changes. The workflow adds no diagnostic code: what it reports about itself is
> carried in the columns below, because a gate that failed is a property of one
> combination at one temperature and not an event.

---

## 1. Configuration

```text
workflow
  count                 "data"     FR-080. "data" or "peaks"
  peaks_multi_start     12         the peaks rule: starts for its fit
  peaks_fit_budget_s    120        the peaks rule: seconds for its fit (C16)
  max_per_sign          4          FR-082: the count may grow past the bound
                                   to this many per sign (C17)
  window_factor         3          AC-030, either side of the extreme peaks
  residual_factor       2          AC-026
  spread_max            0.01       AC-027
  share_min             0.001      AC-028, of the zero-field conduction
  search_multi_start    12         starts per combination during the search
  final_multi_start     24         starts for the released refit
  fit_budget_s          30         AC-029, seconds for one fit; 0 removes it
  loop_tolerance        0.01       the peaks rule: stop when the fitted
                                   densities and mobilities move less than this
  loop_max_iterations   10         the peaks rule: and never more than this
  fixed_counts          {}         FR-090. {"<T>" or "<low-high>": [holes,
                                   electrons]}, at most 8 carriers in total;
                                   the narrowest range covering a sweep wins
  smooth_band           []         FR-112. [{"range": "<T>" or "<low-high>",
                                   "strength": weak|normal|strong}]. Each band
                                   is held to one count by fixed_counts and
                                   then coupled across temperature (FR-027).
                                   A band of fewer than three temperatures, or
                                   one whose sweeps do not share a count, is
                                   refused
  smooth_multi_start    1          AC-040. Starting points for a coupled
                                   refit. It begins from an answer already
                                   found, so further randomised starts re-solve
                                   a solved problem

optimization
  fit_budget_s          30         FR-088, the same budget for any fit
  global_budget_s       1800       AC-039, seconds for one coupled fit over a
                                   whole band; 0 removes it. Separate from
                                   fit_budget_s, whose 30 s would expire every
                                   start of a coupled fit
```

`count` is the one setting that changes what the answer *claims* rather than
how it is reached, and every result is printed with the rule that set its count
and what it can claim (FR-081).

---

## 2. Output files

Written only when a count rule is requested. The files of features 001 to 003 are
unchanged and are still written.

| File | One row per | Carries |
| --- | --- | --- |
| `workflow_summary.csv` | temperature | count rule, combination, whether it lies past the spectrum's bound, grade, residual over noise and runs test of both channels, the noise of each, `R^2` of both channels, RMSE of both channels, condition number, spread, gates failed, carriers outside the window, a better-fitting combination that does not reproduce and how many times better, feedback iterations, why the loop stopped, seconds |
| `workflow_carriers.csv` | fitted carrier | temperature, name, kind, density in cm^-3, mobility in cm^2/Vs, share of the zero-field conduction, `mu B` at 9 T |
| `workflow_candidates.csv` | combination tried | temperature, holes, electrons, RMSE of both channels, condition number, spread, weakest share, on a bound, out of budget, seconds |
| `report.html` | run | the page of FR-092 |

Under the peaks rule the gates are evaluated and reported but choose nothing;
a temperature where it found no peak, or no fit finished, has no carriers and
is never a pass. An infinite residual is a combination whose every start ran out of
budget.

---

## 3. The report page

One file, openable with no network connection. Its order is part of the
requirement:

1. the verdict per temperature: combination, grade, and the gates failed
2. for a chosen temperature, the measurement against the fit in both channels
3. the density and mobility of every carrier against temperature
4. every combination tried

Every label on the page comes from `mbfit/messages.py` and is passed into the
generator, which keeps the generator ASCII under Article IV.
