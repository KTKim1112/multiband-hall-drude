# Specification — Multiband Magnetotransport Analysis

Feature 001 · Version 1.0.0 · 2026-08-26

Derived from the received `SDD_SPEC_KR.md`. Requirements are renumbered and
subdivided so that each one is reachable from at least one task and one test.
This document names no technology; see `plan.md` for those choices.

---

## 1. Purpose

A researcher has measured, on one sample, the longitudinal resistivity and the
Hall resistivity as a function of magnetic field, at several temperatures. They
wish to know how many charge carriers of each sign are present, and what
density and mobility each carries, as a function of temperature — and, equally
important, **how much of that answer the data actually determines.**

The program takes such a data set and a declaration of what is believed about
the sample, fits a classical independent-carrier model, and returns the fitted
parameters together with the evidence for and against trusting them.

## 2. Who uses it and what they need

| Need | Requirement |
| --- | --- |
| Their columns are not named the way anybody else names them | FR-003 |
| The number of bands is not known in advance and must be varied | FR-011 |
| Half the analysis is deciding whether the answer is unique | FR-043 to FR-048 |
| The result must be reproducible and citable a year later | FR-037, NR-005 |
| The analysis must be repeatable by somebody else from the record alone | FR-037 |

## 3. Terms

- **Carrier** — one population of charge carriers of a single sign, described
  by a density and a mobility. Called a *band* or a *pocket* informally.
- **Channel** — one of the two measured quantities: longitudinal or Hall.
- **Space** — the pair of quantities the comparison is made in: the measured
  resistivities, or the conductivities derived from them.
- **Strategy** — how the temperatures relate to one another during fitting.

---

## 4. Physical model contract

Each carrier `i` is an independent classical Drude channel with density `n_i`,
mobility `mu_i`, and charge sign `s_i` (electron `-1`, hole `+1`). With the
field along `z`:

```text
sigma_xx = SUM_i  n_i q mu_i / [1 + (mu_i B)^2]
sigma_xy = SUM_i  s_i n_i q mu_i^2 B / [1 + (mu_i B)^2]
```

where `q` is the elementary charge, a positive number.

The resistivity tensor is the matrix inverse of the conductivity tensor:

```text
rho_xx = +sigma_xx / (sigma_xx^2 + sigma_xy^2)
rho_xy = +sigma_xy / (sigma_xx^2 + sigma_xy^2)
```

**PM-001.** For a single carrier the model must reduce exactly to

```text
rho_xx = 1 / (n q mu)                       field independent
rho_xy = B / (n q_signed),  q_signed = s q
```

so that at positive field a single electron band gives **negative** `rho_xy`
and a single hole band gives **positive** `rho_xy`.

> **Correction to the received specification.** `SDD_SPEC_KR.md` section 4
> paired `s(electron) = -1` with `rho_xy = -sigma_xy / (...)`. The two belong
> to opposite sign conventions, and their product inverts the Hall sign: the
> inherited prototype reports an electron-dominated sample as hole-dominated,
> with no change to the fit quality. Measured and recorded in `research.md`
> section 2.1. The minus sign in the inversion is removed here; `s` is
> unchanged.

**PM-002.** A configurable field polarity multiplies `rho_xy` and reverses its
sign, for experiments whose transverse contacts are wired oppositely. Its
default leaves the model at PM-001.

**PM-003.** The model is symmetric under exchanging any two carriers of the
same sign. The program does not assume a carrier keeps its identity across
temperatures, and says so in its output. See FR-047.

---

## 5. Functional requirements

### 5.1 Data intake

- **FR-001** The program shall accept a data set of records, each carrying a
  temperature, a magnetic field, a longitudinal resistivity and a Hall
  resistivity.
- **FR-002** One data set may contain many temperatures. The program shall
  group the records by temperature and treat each group as one field sweep.
- **FR-003** The names by which the four quantities appear in the data set
  shall be declarable externally, without modifying the program.
- **FR-004** A data set lacking any of the four quantities shall be rejected,
  naming every quantity that is missing.
- **FR-005** Records with absent or non-numeric values shall be discarded, and
  the number discarded shall be reported rather than silently absorbed.
- **FR-006** A temperature group producing fewer **residuals** than there are
  free parameters shall be reported as underdetermined before fitting begins.
  The residual count is not the record count: it is the record count times the
  number of channels FR-018 selected. One hundred records give two hundred
  residuals when both channels are fitted and one hundred when one is.

### 5.2 Preprocessing

- **FR-007** A multiplicative correction factor on the Hall resistivity shall
  be applicable, for data recorded with a known calibration error.
- **FR-008** The longitudinal resistivity shall optionally be replaced by its
  even part in field, `[r(B) + r(-B)] / 2`.
- **FR-009** The Hall resistivity shall optionally be replaced by its odd part
  in field, `[r(B) - r(-B)] / 2`.
- **FR-010** When FR-008 or FR-009 is requested and the record at the opposite
  field is absent, the program shall obtain the opposite-field value by
  interpolation where the sweep brackets it, leave the record untouched where
  it does not, and report the count of each case.

### 5.3 Carrier topology

- **FR-011** The number of carriers shall be declarable externally, without
  modifying the program. At least one carrier is required; the program imposes
  no upper limit.
- **FR-012** Each carrier shall declare a sign, electron or hole, and a name
  unique within the declaration.
- **FR-013** Any mixture of electron and hole carriers shall be permitted,
  including all of one sign.

### 5.4 Parameters and their domain

- **FR-014** Each carrier shall carry, independently: an initial density, a
  lower and an upper bound on density, an initial mobility, and a lower and an
  upper bound on mobility.
- **FR-015** An initial value outside its own bounds shall be rejected before
  fitting begins, naming the carrier and the quantity.
- **FR-016** Initial values shall be overridable for individual temperatures,
  so that a known result at one temperature can seed the analysis.
- **FR-017** Bounds are a declaration of the physically admissible domain, not
  a numerical convenience. The program shall record them in its output and
  report every parameter that comes to rest against one. See FR-043.

*Appended 2026-08-26.*

- **FR-054** Bounds, as well as initial values, shall be overridable for
  individual temperatures. Every override shall be reported as a diagnostic
  naming the temperature, the carrier, the quantity and both the default and
  the overriding value, because a bound that varies with temperature is the
  one setting in this program capable of drawing a parameter trajectory by
  hand.

### 5.5 What is compared

- **FR-018** The comparison shall be selectable between: both channels, the
  longitudinal channel alone, and the Hall channel alone.
- **FR-019** The comparison shall be selectable between resistivity space and
  conductivity space. The choice of space applies to whichever channels
  FR-018 selected.
- **FR-020** Each channel shall be normalised by a scale robust to outliers
  before comparison, so that the two channels contribute comparably regardless
  of their units and magnitudes.
- **FR-021** A relative weight for each channel shall be declarable on top of
  FR-020.
- **FR-022** An optional additional emphasis on low field shall be applicable
  to the longitudinal channel, with a declarable strength and a declarable
  field scale.

*Requirement numbers are append-only. FR-049 to FR-051 belong here and were
added on 2026-08-26; they are numbered after FR-048 so that every earlier
reference in the code, the tests and the record stays valid.*

- **FR-049** The range of field admitted to the comparison shall be
  restrictable, by a lower and an upper bound on the magnitude of the field,
  independently of the range that is read, reported and plotted. The
  restriction is off by default.
- **FR-050** Records excluded by FR-049 shall still be predicted, and written
  out with their residual, and their number and field range recorded. The
  excluded region is the evidence for whatever motivated excluding it, and
  the program shall not hide it.
- **FR-051** Fit quality shall be reported separately for the records inside
  and outside the FR-049 restriction, so that the cost of the exclusion is
  visible rather than inferred.

### 5.6 How temperatures relate

- **FR-023** *Independent* — each temperature is fitted with no reference to
  any other.
- **FR-024** *Sequential* — temperatures are fitted in ascending order and the
  result at one temperature becomes the initial value at the next. **This is
  all it does.** No penalty couples the temperatures; each is still a separate
  optimisation, and the objective at each temperature is exactly the one
  FR-023 uses.
- **FR-025** *Global* — all temperatures are fitted as a single problem, so
  that a penalty coupling adjacent temperatures can act. **The coupling
  penalties of section 5.7 exist only here.**
- **FR-026** The strategy shall be selectable, and the program shall record
  which was used.

> **Seeding and coupling are different things and are kept apart.** Sequential
> changes only where the search starts; global changes what is being
> minimised. A configuration that asks for a coupling penalty without the
> global strategy is rejected rather than silently ignored, so that a Methods
> section can state which of the two was in force without ambiguity.

### 5.7 Temperature coupling

- **FR-027** The coupling penalty shall be switchable off entirely.
- **FR-028** Density and mobility shall have independent coupling strengths,
  either of which may be zero.
- **FR-029** The penalty shall be selectable between penalising the change of
  a parameter between adjacent temperatures, and penalising the change of its
  rate of change.
- **FR-030** Each carrier shall be includable in or excludable from the
  coupling, separately for density and for mobility.
- **FR-031** The penalty shall be correct for unequally spaced temperatures. A
  data set measured every 2 K below 20 K and every 20 K above shall not be
  penalised differently on that account alone.
- **FR-032** An optional monotonic expectation — none, increasing, or
  decreasing with temperature — shall be declarable per carrier, separately
  for density and mobility. It shall act as a penalty that a sufficiently
  insistent data set can overcome, never as a hard constraint.

*Appended 2026-08-26. FR-052 and FR-053 belong in this section.*

- **FR-052** The coupling and monotonic penalties shall act on carriers
  ordered canonically within each sign, not on the order in which they were
  declared. PM-003 makes the declared order meaningless, so a penalty applied
  by declaration index would silently assert that a carrier keeps its identity
  across temperature. Whenever either penalty is active the program shall
  report every temperature step at which the canonical order changed, so that
  the assertion the penalty does make is visible.
- **FR-053** The coupling shall be breakable at declared temperatures. A
  penalty spanning a phase transition asserts continuity where the sample
  provides none; the program shall allow the temperature series to be cut so
  that no penalty term crosses a declared break.

### 5.8 Robustness of the search

- **FR-033** The search shall be repeatable from several starting points,
  their number declarable, the best result retained.
- **FR-034** The dispersion of the starting points shall be declarable.
- **FR-035** The comparison shall optionally down-weight large residuals, with
  the down-weighting function selectable, so that isolated bad records do not
  dominate.
- **FR-036** Every result from FR-033 shall be retained, not only the best, so
  that FR-045 can examine them.

### 5.9 What is produced

- **FR-037** The complete configuration actually used — every declared value,
  every default that filled a gap, and the random seed — shall be written out
  in a form that reproduces the run exactly.
- **FR-038** For each temperature: the measured, fitted and residual values of
  both channels, in both spaces.
- **FR-039** For each temperature: the fitted density and mobility of every
  carrier.
- **FR-040** For each temperature: the fit quality of each channel, by at
  least a coefficient of determination and a root-mean-square residual.
- **FR-041** Figures showing measurement and fit together, per temperature and
  per channel, and the fitted parameters against temperature.
- **FR-042** A diagnostics report, in one place, listing every violation
  detected under section 5.10.

### 5.10 Diagnostics — the evidence against trusting the answer

- **FR-043** Report every fitted parameter resting within a declarable
  fraction of one of its bounds.
- **FR-044** Report every parameter that changes between adjacent temperatures
  by more than a declarable factor.
- **FR-045** Report when the starting points of FR-033 reach materially
  different parameter sets of indistinguishable fit quality, listing the
  distinct sets found.
- **FR-046** Report when a residual retains systematic structure in field
  rather than resembling scatter.
- **FR-047** Report when two carriers of the same sign appear to have
  exchanged roles between adjacent temperatures, since PM-003 makes such an
  exchange free of cost.
- **FR-048** Every diagnostic shall state the quantity measured, the threshold
  it crossed, and where that threshold came from.

*Appended 2026-08-26.*

- **FR-056** Every soft prior in force shall announce itself in the
  diagnostics, stating its strength and what it applied to: the coupling
  penalty with its order, its two strengths, the carriers it covered and the
  breaks it respected; the monotonic expectation with its direction per
  carrier; the low-field emphasis; and any down-weighting of large residuals.
  A result never appears without the priors that shaped it appearing beside
  it. The field window already does this under FR-049, and there is no reason
  for a penalty to be quieter than a truncation.
- **FR-057** A single switch shall disable every soft prior at once, without
  editing the declared configuration, so that the check Article X requires —
  whether the conclusion survives removing the constraint — is one run away
  rather than an edit away. It disables exactly the soft priors, being the
  coupling penalty, the monotonic expectation, the low-field emphasis and the
  robust down-weighting; it does not touch the hard constraints, being the
  declared bounds and the field window, which are statements about the
  admissible domain rather than preferences within it. The configuration
  written out under FR-037 records the values that were **in force**, not the
  values that were declared, so a run made with the switch reproduces without
  it.
- **FR-055** The conditioning of the converged problem shall be measured and
  reported: the singular values of the derivative of the residual with respect
  to the fitted parameters, and their ratio. Where the ratio exceeds a
  declarable value, report it. This measures directly what FR-043 to FR-047
  each measure a symptom of — whether the data determines the parameters —
  and unlike them it does not depend on the search having been repeated, on
  the temperatures being adjacent, or on a carrier being slow.

---

## 6. Numerical requirements

- **NR-001** Densities and mobilities are strictly positive at every stage of
  the search. Zero and negative values never enter the model.
- **NR-002** The search operates on the logarithm of each parameter, so that a
  step is a fractional change and the search is invariant to the units the
  parameters are declared in.
- **NR-003** The coupling penalties of section 5.7 act on the logarithm of the
  parameters, so that a change from 1 to 2 and a change from 100 to 200 are
  penalised equally.
- **NR-004** The unit contract at the boundary of the program: density in
  `cm^-3`, mobility in `cm^2 / (V s)`, both resistivities in `micro-ohm cm`,
  magnetic field in `T`, temperature in `K`. Conductivities are reported in
  `S / m`.
- **NR-005** A run is reproducible. The same data and the same configuration,
  including the seed, produce identical numbers.
- **NR-006** Where the fitted result is at a bound, the reported value is the
  bound itself, not a value slightly beyond it.

---

## 7. Acceptance criteria

**These are project specification, not physical fact.** They are the numbers
this project agrees to be judged by; another project may choose others. Each
is declarable, and the value in force is recorded with the result. See FR-037.

| ID | Criterion | Default |
| --- | --- | --- |
| AC-001 | Coefficient of determination, longitudinal channel | `>= 0.995` |
| AC-002 | Coefficient of determination, Hall channel | `>= 0.995` |
| AC-003 | A parameter within this fraction of a bound raises FR-043 | `0.005` |
| AC-004 | A parameter changing by more than this factor between adjacent temperatures raises FR-044 | `5` |
| AC-005 | Starting points whose fit quality differs by less than this fraction, but whose parameters differ by more than AC-006, raise FR-045 | `0.01` |
| AC-006 | Two parameter sets count as materially different at this relative difference in any one parameter | `0.20` |
| AC-007 | A residual whose runs-test score, taken over the field-ordered residual sequence, falls below this raises FR-046 | `-3` |
| AC-009 | With FR-049 in force, a ratio of root-mean-square residual outside the fitted window to inside above this is reported | `3` |
| AC-010 | A ratio of largest to smallest singular value above this raises FR-055 | `1000` |

> AC-007 originally counted the lag-1 autocorrelation of the residual and
> triggered above `0.5`. Measured on the reference data set of research 2.4,
> that criterion is useless: at 0.05 T spacing neighbouring residuals are
> correlated whatever the model does, and the supplied fit scores close to the
> maximum. The runs test separates the cases — the same residual gives a
> strongly negative score, while a residual that is genuinely scatter gives one
> near zero. The values are recorded in research 4.5 and 4.6, which is measured
> from a sample and is not published with the program.

> **Calibrated against three real sweeps, 2026-09-11.** The sample was measured
> at 5, 20 and 40 K, and research 4.8 measured what a misfit of the size
> present does to the parameters. **No default changed**, and two of them stop
> being proposals. What each criterion was measured against is recorded in
> research 4.8, which is measured from a sample and is not published with the
> program; the verdicts it reached are normative and are here:
>
> | | verdict |
> | --- | --- |
> | AC-001, AC-002 | **inverted.** The best-determined sweep has the worst `R2`. Kept as a floor on convergence only. It is not evidence about the parameters, and research 4.8 measures the size of the gap: reproducible far tighter than it is accurate |
> | AC-004 | **confirmed.** The threshold of `5` falls between an ordinary temperature dependence and the Hall sign change, and fires only at the latter |
> | AC-005, AC-006 | **confirmed, and bounded in meaning.** The optimum is unique for fixed data even where the data barely determines it. These criteria measure the search, not the answer |
> | AC-007 | **confirmed.** All three sweeps are misspecified and all three are reported |
> | AC-010 | **confirmed on real data**, having been set on synthetic data in research 4.6. It fires at the worst-conditioned sweep and nowhere else, which research 4.8 shows is also where a perturbation leaves the linear regime |
>
> AC-003 and AC-009 remain untested against real data: no fit reached a bound,
> and no field window was declared.

**AC-008.** A single-carrier data set generated from known values must return
those values to a relative accuracy of `1e-6`. This is the round trip, and it
is not negotiable. A factor of two, a flipped sign or a missing unit
conversion does not crash anything and is not visible in any residual.

---

## 8. Out of scope

The model is classical, independent-carrier, and field-independent in its
scattering. The following are not represented, and data dominated by them will
be fitted anyway, plausibly, and wrongly:

- field-dependent mobility
- anisotropic scattering time over the Fermi surface
- explicit interband scattering
- quantum corrections, including weak localisation and quantum oscillations
- any separate anomalous Hall term. **The entire Hall signal is attributed to
  the Drude carriers**, deliberately. This is not a claim that no anomalous
  contribution exists in any sample; it is a decision not to introduce a
  component whose presence is disputed for the material at hand. See
  research 6, entry C8
- effective-medium or multi-phase mixtures
- mobility spectrum inversion
- hydrodynamic or nonlocal transport
- open orbits

Representing any of these requires a new specification, not tighter bounds on
this one. Section 5.10 exists so that data of this kind announces itself.

---

## 9. Deliberately excluded from this version

Recorded so that their absence is a decision rather than an oversight. Each is
a candidate for feature 002.

- **Parameter uncertainties**, by covariance, bootstrap or any other route.
  FR-055 reports whether the parameters are determined; it does not say by how
  much they are uncertain.
- **Model comparison across carrier counts.** Any number of carriers can be
  fitted and compared by hand, but the program offers no criterion for
  deciding whether three carriers suffice where four were tried. A criterion
  is needed, since fit quality alone always favours more carriers. Note before
  building one: the usual information criteria assume independent residuals,
  and the residuals measured on the reference data set are strongly
  correlated — a strongly negative runs-test score, recorded in research 4.5. An
  information criterion applied to them would count each correlated run as
  independent evidence and would be over-confident. Whatever is built has to
  face that.
- **Automatic selection of the coupling strength**, by an L-curve or otherwise.
- **Staged fitting**, in which one optimisation over a restricted field range
  and channel weighting seeds a second over the full range. The pieces exist
  separately here — FR-021 weights, FR-022 low-field emphasis, FR-049 field
  window — but they cannot be composed into a sequence within one run. The
  shape a later version would take:

  ```text
  stage 1:  |B| <= 1 T,  weight_rhoxx 1,  weight_rhoxy 0.05
  stage 2:  full range,  weight_rhoxx 1,  weight_rhoxy 0.5,
            initial values taken from stage 1
  ```

  This is deliberately not in feature 001: a single objective is easier to
  state in a Methods section and easier to argue about, and staging is a
  search strategy rather than a statement about the data. When it is built,
  Article X applies to the staging itself, since the answer depends on it.
- **Carrier matching across temperature**, beyond the canonical ordering of
  FR-052. Tracking which carrier is which through a mobility crossing is a
  problem of its own.
