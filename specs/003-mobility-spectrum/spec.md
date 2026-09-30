# Feature 003 — the mobility spectrum, by separating the carrier types first

> English is normative. `docs/003-spec.ko.md` is its translation.
>
> Requirement identifiers continue the project numbering: FR-067 follows
> FR-066, and nothing already issued is reused or renumbered.

---

## 1. Purpose

Feature 001 fits a declared number of carriers and never asks whether that
number is right. This feature asks, by solving for a *distribution* over
mobility instead of a fixed set of carriers, and reporting what that
distribution supports.

The first attempt could not answer: the peak count moved between six and two
with the regularisation strength, because hole and electron contributions
partially cancel in the Hall channel and an inversion that sees only their sum
cannot choose between the splits that fit. Research 003 section 1 measures that
separating the two carrier types first removes the freedom entirely — the same
inversion then returns one answer across every regularisation strength tried.

**So this feature does the separation, and only then the inversion.** What it
produces is a proposal for how many carriers of each sign the measurement
supports, with the evidence for how far that proposal can be trusted.

---

## 2. Who uses it and what they need

A reader deciding whether the carrier count they declared was the right one.
They need:

- the conductivity of each carrier type as a function of mobility,
- a count per sign, with the range of regularisation over which it holds,
- the carriers read off it in units a fit can start from,
- and, above all, the evidence that limits the claim: how well the Lorentzian
  extension described the data, how many of its starting points agreed, and
  whether any separated conductivity lost its sign.

---

## 3. Terms

| Term | Meaning here |
| --- | --- |
| **Normalised channels** | `X = sigma_xx/sigma_xx(0)` and `Y = sigma_xy/sigma_xx(0)`, both dimensionless |
| **Extension** | The sum of `n` Lorentzians fitted to `X` and `Y` together, sharing one set of mobilities |
| **Transform** | The Kramers-Kronig transform of the extension, in closed form |
| **Separation** | Splitting `X` and `Y` into hole and electron parts using the transform |
| **Branch** | One carrier type's inverse problem, and its spectrum |
| **Conductivity density** | `s(mu) >= 0` on a positive grid: the share of `sigma_xx(0)` carried near that mobility |
| **Plateau** | A run of consecutive regularisation strengths returning the same peak count for one branch |
| **Proposal** | How many peaks each branch has. A suggestion, never a decision |

---

## 4. Functional requirements

### 4.1 Normalise and extend

- **FR-067** The program shall normalise both conductivities by `sigma_xx(0)`,
  estimated over a declared low-field window, and shall record the window and
  how many records fell inside it.
- **FR-068** The program shall fit `n` Lorentzian terms to `X` and `Y`
  **simultaneously**, sharing one set of mobilities, from several declared
  starting points, and shall record every term and how many starting points
  reached the best solution.
- **FR-069** The order `n` shall be declared by the reader, recorded, and
  reported. The program shall not infer it. Research 003 section 3.3 measures
  an order below the number of distinct mobilities failing by a factor of
  seven, and section 6.2 measures the order moving the proposal on real data.

### 4.2 Transform and separate

- **FR-070** The transform shall be computed in closed form. **No numerical
  principal-value integral shall appear on the path that produces a result.**
- **FR-071** The program shall separate `X` and `Y` into four non-negative
  parts and shall report, for each, how much of it came out with the wrong
  sign. A wrong-signed part shall be reported, never repaired.

### 4.3 Invert, per carrier type

- **FR-072** The program shall recover a non-negative conductivity density on
  a positive mobility grid, separately for each carrier type, subject to a
  smoothing penalty.
- **FR-073** The program shall select the regularisation strength by the
  discrepancy principle against a declared noise level, and shall report the
  peak count at **every** strength examined, per carrier type. Where a carrier
  type has more than one plateau, or none, it shall say so.
- **FR-074** The program shall read carriers off each branch: a peak's
  mobility from the density's centre, and its density from
  `sigma_xx(0) * S = n q mu`, where `S` is that peak's share of the spectrum.

### 4.4 What may be concluded

- **FR-075** On request, the program shall seed the carrier fit of feature 001
  from those carriers.
- **FR-076** **The carrier count remains the reader's declaration.** The
  proposal is reported beside the evidence limiting it and never overrides the
  declared carriers.
- **FR-077** The report shall carry the extension's mobilities, so that a
  reader can see that every peak sits where the extension put it. The spectrum
  cannot find structure the extension did not admit.
- **FR-078** The harmonic-ladder test of FR-063 shall be applied to carriers a
  fit returned and **never** to the peaks of a spectrum, and no ladder verdict
  shall be reported for spectrum peaks. Research 003 section 7 measures the
  inversion moving a perfect ladder of ratios `1, 2, 3, 4` to `1, 2.10, 3.68`,
  which the test then clears: composing two sound tools gives a single orbit a
  clean bill of health.
- **FR-079** The program shall put the carriers it read off the spectrum back
  through the model of PM-001 and report, per channel, how far the result is
  from the measurement. **The spectrum shall not be reported as a set of
  densities and mobilities without that number beside it.** Research 003
  section 8 measures a synthetic sweep and a real one whose extension
  residuals agree to within a fifth and whose round trips are `3.7 %` and
  `26.8 %`: every check internal to the spectrum passes on both.

---

## 5. Numerical requirements

- **NR-009** The Kramers-Kronig step shall be exact in the Lorentzian basis.
  Truncating an infinite integral shall not be a source of error.
- **NR-010** The conductivity density shall be non-negative at every grid point
  of every branch.
- **NR-011** Each extension term shall decompose into a non-negative hole
  weight and a non-negative electron weight, making the separated
  conductivities non-negative by construction rather than by inspection.
  Research 003 section 3.1 measures what the unconstrained form costs: a
  solution whose fit residual is indistinguishable from a good one, whose
  separated conductivity reaches `-77.7` where its true range is `+0.02` to
  `+0.50`, and which of the two the search finds depends on how many starting
  points it was given. The constraint may be switched off to reproduce the
  published method, and doing so is reported.

---

## 6. Physical model contract

No change. The spectrum is the model of PM-001 with the carrier sign carried by
which separated part is being inverted. Research 003 section 2.2 checks the
extension against the model of feature 001 rather than assuming it, and section
2.4 records a sign in the published equations that this project does not
follow.

---

## 7. Acceptance criteria

| ID | Criterion | Default |
| --- | --- | --- |
| AC-017 | Mobility grid points per decade | `40` |
| AC-018 | Residual norm, as a multiple of the expected noise, counting as reaching it | `1.1` |
| AC-019 | A local maximum below this fraction of the largest, or carrying less than this share of the whole spectrum, is not a peak | `0.02` |
| AC-020 | Consecutive strengths returning the same count to call it a plateau | `3` |
| AC-021 | Extension residual above this multiple of the noise is reported | `10` |
| AC-025 | Round-trip error, per channel, above which the spectrum's carriers are reported as not describing the sweep | `0.05` |

**AC-022.** A spectrum recovered from synthetic data generated by a known
carrier set shall return one peak per carrier per branch, of the right sign,
each mobility within `5 %` and each density within `5 %`, at the strength the
discrepancy principle selects. This is the round trip for this feature.
Research 003 section 4 measured `1.9 %` and `1.8 %` noiseless, and `4.1 %` and
`3.2 %` at the noise this project's sweeps actually carry.

**AC-023.** The separated parts shall recombine to the measurement to `1e-10`
relative. This is algebra and must hold whatever the fit quality; when it
fails, the fault is in the separation and not in the physics.

**AC-024.** No separated part shall have a wrong-signed fraction above `0.01`
while NR-011 is in force.

> The `0.05` of AC-025 sits between what the method achieves when the model
> holds and what it achieves here. Research 003 section 8 measures `0.14 %`
> noiseless, `2.2 %` at the noise these sweeps carry and `3.7 %` at four times
> that, against `9 %` to `27 %` on the real sweeps.

---

## 8. Out of scope

- **Deciding the carrier count.** FR-076 is deliberate. Research 003 section
  6.2 measures the proposal moving with the extension order on real data, so a
  program that chose would be choosing on the reader's behalf without the
  evidence to do it.
- **Removing an oscillatory component before the extension.** Research 003
  section 6.1 measures a residual floor of `4.7 %` that more terms do not
  reduce, and Q9 asks whether that floor is quantum oscillation. Answering it
  needs a background model this feature does not have.
- **The published outer loop** — refit, return to the extension, repeat. It has
  no stated convergence criterion, and with the count declared by the reader
  its main purpose is already served. Recorded as Q12.
- **Maximum-entropy regularisation**, recorded as Q10.

---

## 9. Deliberately excluded from this version

- **Automatic detection of a single orbit from the spectrum.** FR-078 forbids
  the obvious route, and nothing replaces it here. Research 002 section 4's
  test remains the way to ask that question, and it is asked of the fitted
  carriers.
- **Uncertainties on the proposed carriers.** Feature 002 resamples the
  residual of a fit; nothing here resamples the spectrum. A peak's mobility and
  density are reported as the point values they are, and the interval a reader
  should quote comes from fitting those carriers and resampling that.
