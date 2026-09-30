# Feature 002 — uncertainty, and whether multiband is the right reading

> English is normative. `docs/002-spec.ko.md` is its translation.
>
> This document states requirements, not technology. It continues the
> numbering of feature 001: requirement identifiers are append-only across the
> project, so FR-058 follows FR-057 and nothing already issued is reused or
> renumbered.

---

## 1. Purpose

Feature 001 reports carriers and reports whether they are *determined*. It
does not report **by how much they are uncertain**, and it offers no way to
ask whether the multiband reading is the right one rather than a
Fermi-surface geometry wearing multiband clothes.

Research 001 section 4.8 measured the size of the gap: the 5 K carriers repeat
to `0.000 %` across 60 starting points and are accurate to something of order
`5` to `15 %`. A reader given only the first number will quote four
significant figures for a quantity known to one. **Closing that gap is what
this feature is for.**

---

## 2. Who uses it and what they need

The same reader as feature 001, now writing a Methods section. They need
three things this project does not yet give them:

- an interval to put after each number, and an honest statement of what the
  interval does and does not cover,
- the knowledge of **which combinations** of the parameters are determined,
  since research 002 section 3.4 measured that the total densities are four
  times better known than the individual carriers and their difference six
  times worse,
- a defence against the reviewer who asks whether four channels are four bands
  or one non-circular orbit.

---

## 3. Terms

| Term | Meaning here |
| --- | --- |
| **Resampling interval** | A parameter interval obtained by refitting data rebuilt from the model plus a resample of the residual |
| **Block length** | The number of consecutive residual points moved together when resampling, which preserves correlation up to that scale |
| **Derived quantity** | A function of the fitted parameters reported with its own interval: a total, a ratio, a difference |
| **Harmonic ladder** | Channel mobilities standing in ratios of consecutive small integers with monotonically falling weight and a single sign, the signature of one non-circular orbit read as several carriers |
| **Parity of a channel** | Even in `B` for the longitudinal channel, odd for the Hall channel |

---

## 4. Functional requirements

### 4.1 Resampling interval

- **FR-058** The program shall report, for every fitted parameter at every
  temperature, an interval obtained by resampling the residual of the
  converged fit, refitting, and taking the spread of the result.
- **FR-059** The resampling shall move **contiguous blocks** of the
  field-ordered residual, of a declared length, rather than individual points.
  The length in force shall be recorded with the result.
- **FR-060** The program shall report the interval **together with** the
  residual-structure diagnostic of FR-046, and shall state that where FR-046
  fires the interval is a **lower bound**. Research 002 section 3.2 measured
  the independent resample understating the counterfactual accuracy of
  research 001 section 4.8 by about three times on this sample.
- **FR-061** The program shall report intervals for the derived quantities as
  well as for the parameters: the total density of each carrier sign, their
  ratio, and their difference.
- **FR-062** The program shall report the correlation matrix of the resampled
  parameters. Research 002 section 3.3 measured this to be stable where the
  interval width is not.

### 4.2 Fermi-surface discriminant

- **FR-063** The program shall test the fitted channel mobilities against the
  harmonic ladder of research 002 section 4, and shall report which of the
  three conditions — integer ratios, falling weights, single sign — hold.
- **FR-064** The report shall state that a fitted mobility is an **effective
  channel mobility** and not the microscopic mobility of a Fermi pocket, on
  every run, whether or not FR-063 finds a ladder.

### 4.3 Intake

- **FR-065** For a sweep supplied with both field polarities, the program
  shall report the **parity violation** of each channel: the norm of the part
  with the wrong parity over the norm of the part with the right one, measured
  before any symmetrisation is applied.
- **FR-066** Where a sweep is supplied with one polarity only, the program
  shall report that the parity violation could not be measured and that any
  contamination of one channel by the other remains in the data.

---

## 5. Numerical requirements

- **NR-007** The comparison shall be made in the space in which the
  measurement noise is additive and independent. Research 002 section 2
  measured that for this instrument that space is resistivity, and measured
  that the choice matters by a factor of 1.4 to 2.6 in parameter accuracy.
  The default of feature 001 therefore stands; what changes is that the
  default now has a criterion behind it rather than a preference.
- **NR-008** The resampling shall not be required to preserve the parity of
  the channel it perturbs. Research 002 section 3.1 measured that the
  Jacobian projects a perturbation onto the parity of its channel, so the
  other half changes the cost and not the answer.

---

## 6. Physical model contract

No change. PM-001, PM-002 and PM-003 are carried over unmodified, and
research 002 section 5.1 records an external proposal to invert PM-001 that is
**rejected on measurement**.

---

## 7. Acceptance criteria

| ID | Criterion | Default |
| --- | --- | --- |
| AC-011 | Number of resamples | `200` |
| AC-012 | Block length, in records | `20` |
| AC-013 | Interval reported, as a fraction of the resampled distribution | `0.68` |
| AC-014 | Two mobilities count as standing in an integer ratio at this relative tolerance | `0.05` |
| AC-015 | A parity violation above this fraction is reported | `0.02` |

**AC-012 is a declaration, not a discovery.** Research 002 section 3.2
measured the interval spanning a factor of five between block lengths 1 and
240, and no argument in this project fixes the value. `20` is chosen as the
scale at which the measured interval reaches the independent estimate of
research 001 section 4.8, and FR-059 requires it to be recorded so that a
reader can see what was assumed.

**AC-016.** A resampling interval computed on data whose residual is pure
independent noise shall contain the generating parameters at approximately the
declared rate of AC-013. This is the round trip for this feature, and it is
not negotiable: an interval that does not cover is not an interval.

---

## 8. Out of scope

- **Choosing the number of carriers.** Feature 001 section 9 defers this, and
  research 002 section 5.4 measures why the usual information criteria cannot
  do it here. Held-out error and field-window stability remain the route.
- **Mobility-spectrum analysis** and the Chambers false-positive test. Large
  enough to be feature 003, and research 002 section 5.5 records the specific
  hazard of running a spectrum on a residual as systematic as this one.
- **Sample-to-sample and Kohler comparison.** Both need data this project does
  not have: a second crystal, and a temperature series longer than three
  points that do not span a sign change.
- **Field-dependent mobility.** The Onsager restriction that `mu(-B) = mu(B)`,
  so that odd powers of `B` are forbidden, is recorded here and is to be
  enforced by whatever feature first introduces such a model. There is no such
  model in features 001 or 002, so there is nothing yet to enforce it on.

---

## 9. Deliberately excluded from this version

- **Profile likelihood.** The correlation matrix of FR-062 answers the same
  question more cheaply for the cases measured here.
- **Markov-chain sampling of the posterior.** It would require a likelihood,
  and research 002 section 3.2 measured that the residual is not the
  independent noise such a likelihood would assume.
- **An interval on the misspecification itself.** Research 001 section 4.8
  obtains one by counterfactual, and it requires a choice of counterfactual
  shapes that the program cannot make for the user.
