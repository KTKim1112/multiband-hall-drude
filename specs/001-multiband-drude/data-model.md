# Data model — structures, the configuration document, and error codes

Feature 001 · 2026-08-26

---

## 1. Structures

Described by content, not by the syntax of any language. Field names are the
names used in the source.

### 1.1 `CarrierSpec` — one declared carrier

| Field | Type | Constraint | Requirement |
| --- | --- | --- | --- |
| `name` | text | non-empty, unique within the run | FR-012 |
| `kind` | `electron` or `hole` | | FR-012 |
| `n_init_cm3`, `n_min_cm3`, `n_max_cm3` | number | `0 < min <= init <= max` | FR-014, FR-015 |
| `mu_init_cm2Vs`, `mu_min_cm2Vs`, `mu_max_cm2Vs` | number | `0 < min <= init <= max` | FR-014, FR-015 |
| `smooth_density`, `smooth_mobility` | true/false | | FR-030 |
| `monotonic_density`, `monotonic_mobility` | `none`, `increase`, `decrease` | | FR-032 |

Derived, not stored: `sign` = `-1` for electron, `+1` for hole. Article V is
why every numeric field carries its unit in its name.

### 1.2 `ResolvedConfig` — the configuration after defaults are filled in

Every value the run used, including defaults the user did not write and the
seed actually drawn. Written out verbatim (FR-037); feeding it back in
reproduces the run bit for bit (NR-005). Contents are section 2.

### 1.3 `TemperatureGroup` — one field sweep

| Field | Meaning |
| --- | --- |
| `T_K` | the temperature of this group |
| `B_T` | field values, ascending |
| `rhoxx_uohmcm`, `rhoxy_uohmcm` | measured, after preprocessing |
| `in_fit_window` | true where the record enters the comparison, false where FR-049 excluded it. Excluded records stay in the group; they are not deleted | FR-049, FR-050 |
| `n_records_dropped` | records discarded under FR-005 |
| `n_mirror_interpolated`, `n_mirror_absent` | counts under FR-010 |

### 1.4 `StartResult` — the outcome of one starting point

| Field | Meaning | Requirement |
| --- | --- | --- |
| `start_index` | 0 is the declared initial value; the rest are perturbed | FR-033 |
| `params` | fitted densities and mobilities, in boundary units | |
| `cost` | the objective value reached | |
| `converged` | whether the solver reported success | |

All of them are kept, not only the best (FR-036), because FR-045 has nothing
to compare against otherwise.

### 1.5 `TemperatureFit` — the answer at one temperature

| Field | Meaning | Requirement |
| --- | --- | --- |
| `T_K` | | |
| `params` | the retained best, in boundary units | FR-039 |
| `params_canonical` | same, sorted by decreasing mobility within each sign | research 4.4 |
| `starts` | every `StartResult` | FR-036 |
| `channel_scales` | the normalisation actually applied to each channel | research 5.4 |
| `r2_rhoxx`, `r2_rhoxy`, `rmse_rhoxx`, `rmse_rhoxy` | over the fitted window | FR-040 |
| `r2_outside`, `rmse_outside` | the same, over the records FR-049 excluded; absent when nothing was excluded | FR-051 |
| `singular_values`, `condition_number` | of the residual derivative at the solution, in log parameters | FR-055 |
| `at_bound` | which parameters rest on a bound, and which bound | FR-043 |

### 1.6 `Diagnostic` — one detected violation

Article VI requires the result to travel with its violations, and FR-048
requires each to state what it measured and where its threshold came from.

| Field | Meaning |
| --- | --- |
| `code` | stable identifier, section 3.4 |
| `severity` | `warning` or `note` |
| `where` | temperature, carrier and quantity, as applicable |
| `measured` | the number that triggered it |
| `threshold` | the number it crossed |
| `threshold_source` | which acceptance criterion, e.g. `AC-004` |

No sentence for a human appears here. Article IV: the presentation layer holds
the Korean wording, keyed by `code`.

### 1.7 `RunResult` — everything the run produced

`ResolvedConfig`, the `TemperatureFit` for every temperature, every
`Diagnostic`, the elapsed time, and the seed used (Article VII).

---

## 2. The configuration document

One document, supplied by the user. Unknown fields are rejected rather than
ignored, so that a typo in an option name cannot silently leave a default in
force. Every field below has a default except `carriers` and `columns`.

```text
schema_version            text, "1.0"

_run                      written by the program, never read.      FR-037
                          Provenance: the strategy that ran, the
                          temperatures, the seed, the conditioning.
                          Accepted and ignored on input so that the
                          emitted document feeds straight back in

columns                   the four names as they appear in the data
  T, B, rhoxx, rhoxy                                          FR-003

model
  hall_polarity           +1 or -1, default +1                PM-002

preprocess
  rhoxy_scale             number, default 1.0                 FR-007
  symmetrize_rhoxx        default false                       FR-008
  antisymmetrize_rhoxy    default false                       FR-009
  mirror_interpolate      default true                        FR-010
  mirror_tolerance_T      default 1e-9, when a field counts
                          as the exact mirror of another

carriers                  list, at least one                  FR-011
  name, kind
  density   { init, min, max }                                FR-014
  mobility  { init, min, max }                                FR-014
  smooth_density, smooth_mobility     default true            FR-030
  monotonic_density, monotonic_mobility  default "none"       FR-032

initial_by_temperature    optional, keyed by temperature      FR-016
  <T> : { <carrier name> : { density, mobility } }

overrides_by_temperature  optional, keyed by temperature      FR-054
  <T> : { <carrier name> : { density  { init, min, max },
                             mobility { init, min, max } } }
                          any field may be omitted; every one
                          supplied raises D_BOUND_OVERRIDE

optimization
  fit_mode                "both" | "rhoxx" | "rhoxy"          FR-018
  fit_space               "rho" | "sigma"                     FR-019
  weight_rhoxx            default 1.0                         FR-021
  weight_rhoxy            default 1.0                         FR-021
  low_field_weight                                            FR-022
    enabled               default false
    alpha                 default 5.0
    B0_T                  default 1.0
  fit_field_range                                             FR-049
    enabled               default false
    abs_min_T             default 0.0
    abs_max_T             null by default, meaning no upper
                          bound. JSON has no infinity, and the
                          resolved document has to round trip
  temperature_strategy    "independent" | "sequential"
                          | "global_smooth"                   FR-023..26
  multi_start             integer >= 1, default 8             FR-033
  multi_start_log_sigma   default 0.25                        FR-034
  random_seed             integer, default 12345              NR-005
  loss                    "linear" | "soft_l1" | "huber"
                          | "cauchy" | "arctan", default
                          "linear"                            FR-035
  f_scale                 default 1.0                         FR-035
  max_nfev, ftol, xtol, gtol   solver limits

smoothing                                                     FR-027..31
  enabled                 default false. Requires
                          temperature_strategy global_smooth  FR-024, FR-025
  order                   1 or 2, default 2                   FR-029
  lambda_density          default 0.0                         FR-028
  lambda_mobility         default 0.0                         FR-028
  breaks_K                list of temperatures, empty by      FR-053
                          default. No penalty term spans one

monotonic_penalty                                             FR-032
  enabled                 default false
  lambda                  default 10.0

acceptance                                                    section 7 of spec
  r2_rhoxx_min            default 0.995                       AC-001
  r2_rhoxy_min            default 0.995                       AC-002
  bound_fraction          default 0.005                       AC-003
  jump_factor             default 5.0                         AC-004
  cost_equivalence        default 0.01                        AC-005
  parameter_difference    default 0.20                        AC-006
  residual_runs_z         default -3.0                        AC-007
  excluded_rms_ratio      default 3.0                         AC-009
  condition_number_max    default 1000.0                      AC-010

output
  make_plots              default true                        FR-041
  plot_dpi                default 180
```

`--no-priors` on the command line sets `smoothing.enabled`,
`monotonic_penalty.enabled` and `low_field_weight.enabled` to false and
`optimization.loss` to `linear`, whatever the document declared (FR-057).
The emitted `resolved_config.json` carries the values that were in force, so
feeding it back reproduces the run without the switch.

**Defaults chosen to be inert.** `smoothing.enabled`, `monotonic_penalty` and
`low_field_weight` all default off, and both smoothing strengths default to
zero. A user who declares only carriers and columns gets the unconstrained
diagnostic fit of stage A in the recommended workflow, which is the honest
starting point. Article X applies to turning any of them on.

---

## 3. Error codes

Article IV: functions signal failure by a code, never by a sentence. Tests
assert on the code. The Korean wording lives in the presentation layer, keyed
by the code, and may be rewritten without touching a test.

### 3.1 Configuration — `E_CONFIG_*`

| Code | Raised when | Requirement |
| --- | --- | --- |
| `E_CONFIG_UNREADABLE` | the document cannot be parsed | |
| `E_CONFIG_SCHEMA_VERSION` | `schema_version` is absent or unsupported | |
| `E_CONFIG_UNKNOWN_FIELD` | a field name is not in section 2 | |
| `E_CONFIG_MISSING_FIELD` | `columns` or `carriers` absent | FR-003, FR-011 |
| `E_CONFIG_BAD_VALUE` | a value is outside its allowed set or range | |
| `E_CONFIG_NO_CARRIERS` | the carrier list is empty | FR-011 |
| `E_CONFIG_DUPLICATE_CARRIER` | two carriers share a name | FR-012 |
| `E_CONFIG_BAD_CARRIER_KIND` | `kind` is neither electron nor hole | FR-012 |
| `E_CONFIG_BOUNDS_INVALID` | `min <= 0`, or `min > max` | NR-001, FR-014 |
| `E_CONFIG_INIT_OUT_OF_BOUNDS` | an initial value lies outside its bounds | FR-015 |
| `E_CONFIG_EMPTY_FIELD_WINDOW` | the FR-049 bounds leave no record in some temperature group | FR-049 |
| `E_CONFIG_COUPLING_WITHOUT_GLOBAL` | a coupling or monotonic penalty is enabled with a strategy other than global | FR-024, FR-025 |
| `E_CONFIG_BREAK_OUTSIDE_RANGE` | a declared coupling break lies outside the temperatures present | FR-053 |
| `E_CONFIG_UNKNOWN_CARRIER` | `initial_by_temperature` names a carrier that was not declared | FR-016 |

### 3.2 Data — `E_DATA_*`

| Code | Raised when | Requirement |
| --- | --- | --- |
| `E_DATA_UNREADABLE` | the data set cannot be read | |
| `E_DATA_MISSING_COLUMN` | a declared column name is absent; every missing name is listed | FR-004 |
| `E_DATA_EMPTY` | no usable record survives | FR-005 |
| `E_DATA_UNDERDETERMINED` | a temperature group has fewer records than free parameters | FR-006 |

### 3.3 Fitting — `E_FIT_*`

| Code | Raised when |
| --- | --- |
| `E_FIT_NO_START` | every starting point failed |
| `E_FIT_SINGULAR` | `sigma_xx^2 + sigma_xy^2` reached zero, so the tensor is not invertible |

### 3.4 Diagnostics — `D_*`

Not failures. Carried in `RunResult` (Article VI) and listed in the report.

| Code | Meaning | Threshold | Requirement |
| --- | --- | --- | --- |
| `D_R2_BELOW` | a channel fell short of its acceptance | AC-001, AC-002 | FR-042 |
| `D_AT_BOUND` | a parameter rests on a bound | AC-003 | FR-043 |
| `D_JUMP` | a parameter jumped between adjacent temperatures | AC-004 | FR-044 |
| `D_NON_UNIQUE` | distinct canonical solutions of equivalent cost | AC-005, AC-006 | FR-045 |
| `D_RESIDUAL_STRUCTURE` | residual retains structure in field | AC-007 | FR-046 |
| `D_LABEL_SWAP` | canonical order changed between adjacent temperatures | none | FR-047 |
| `D_MIRROR_ABSENT` | symmetrisation could not find a mirror record | none | FR-010 |
| `D_RECORDS_DROPPED` | records were discarded on intake | none | FR-005 |
| `D_LOW_MU_B` | a fitted carrier has `mu B < 1` over the whole measured range, so research 4.3 applies to it | `1` | FR-048 |
| `D_EXCLUDED_MISMATCH` | with FR-049 in force, the residual outside the fitted window exceeds the one inside by more than the allowed ratio | AC-009 | FR-051 |
| `D_FIELD_RANGE_ACTIVE` | a field-range restriction was in force; states the bounds and how many records it removed | none | FR-049, FR-050 |
| `D_ILL_CONDITIONED` | the ratio of largest to smallest singular value of the residual derivative exceeds the allowed value | AC-010 | FR-055 |
| `D_BOUND_OVERRIDE` | a bound or initial value was overridden for one temperature; states the default and the override | none | FR-054 |
| `D_PRIORS_ACTIVE` | one entry per soft prior in force, naming it, its strength and its scope. Absent only when no soft prior acted | none | FR-056 |
| `D_PRIORS_DISABLED` | the FR-057 switch was used; lists every prior it silenced and the declared value each had | none | FR-057 |

`D_LOW_MU_B` is not in the received specification. It is added because
research section 4.3 measured a 35 % error on exactly such a carrier while
R-squared stayed above 0.9995, and because it is the one diagnostic that can
be evaluated before the answer is trusted rather than after.

---

## 4. Output files

| File | Contents | Requirement |
| --- | --- | --- |
| `resolved_config.json` | section 1.2 | FR-037 |
| `<T>K_fit.csv` | field, measured, fitted and residual for both channels in both spaces | FR-038 |
| `fit_parameters_vs_T.csv` | density and mobility per carrier per temperature, canonical order alongside declared order | FR-039 |
| `fit_metrics_vs_T.csv` | R-squared and RMSE per channel per temperature | FR-040 |
| `<T>K_rhoxx.png`, `<T>K_rhoxy.png`, `parameters_vs_T.png` | | FR-041 |
| `diagnostics.csv` | every `Diagnostic`, one per row, with its threshold and source | FR-042, FR-048 |
| `multistart_<T>K.csv` | every `StartResult` | FR-036 |
