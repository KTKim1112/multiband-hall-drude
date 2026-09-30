# Feature 004 — the analysis as a procedure, and two rules for the carrier count

> English is normative. `docs/004-spec.ko.md` is its translation.
>
> Requirement identifiers continue the project numbering: FR-080 follows
> FR-079, and nothing already issued is reused or renumbered.

---

## 1. Purpose

Features 001 to 003 supply the pieces: a carrier fit, an uncertainty, a
mobility spectrum. **Nothing in the program says how to use them together.**
The procedure that produced this project's own results lived in a dozen
throwaway scripts, and a reader given the same data could not reproduce it.

This feature makes the procedure a function, and makes the one choice in it
that transport alone cannot settle -- what sets the number of carriers -- a
choice the reader makes, with a default that needs no evidence beyond the sweep.

---

## 2. Who uses it and what they need

Someone with a folder of sweeps who wants carrier densities and mobilities out
of them. They need the program to say **how many carriers** before it says how
many of what — and, where the data does not settle that, to say so instead of
choosing on their behalf.

They also need it to finish. Research 004 section 2 measures a search in which
8 fits of 83 consumed 88 % of the wall clock and every one of those 8 failed
the selection anyway.

---

## 3. Terms

| Term | Meaning here |
| --- | --- |
| **Count rule** | What sets the number of carriers the fit has: the data, or the spectrum's peaks |
| **Window** | The mobility range a carrier type is allowed, taken from the spectrum |
| **Combination** | One choice of how many holes and how many electrons |
| **Gate** | A pass or fail test on a combination |
| **Grade** | How far the parameters of a passing combination can be trusted |
| **Budget** | The wall clock a single fit is allowed before it is abandoned |

---

## 4. Functional requirements

### 4.1 One procedure, two rules for the carrier count

*Amended 2026-09-15.* This section first offered a "spectrum mode" whose answer
was the spectrum's peaks read as carriers, and called it the published
procedure. It is not: Liu et al. (Supplemental Material section III, step 4)
end in a multiband fit started from the peaks. That mode is withdrawn, and
research 004 section 4.2 records the correction and what it measured.

- **FR-080** The program shall run one procedure — the spectrum bounds the
  problem, a multiband fit gives the answer — and shall offer two rules for the
  carrier count:
  - **data** — the spectrum's peak count per sign is an upper limit and the
    window of FR-082 a range. Every combination up to the limit is fitted and
    one is selected by FR-085. The answer is the smallest set of conduction
    channels the sweep requires, with parameters it determines.
  - **peaks** — the count is the spectrum's peak count, held. The peak values
    start the fit, the fit is fed back into the extension, the spectrum is
    recomputed, and the loop repeats until the fitted densities and mobilities
    converge. The answer is the converged fit, graded by AC-031, with the gates
    of FR-085 reported and choosing nothing.

  The data rule shall be the default. The peaks rule rests on a count the data
  does not determine, and needs evidence from outside transport before its
  count is quoted.
- **FR-081** The program shall report with every answer which rule set the
  count and what that answer can claim. Under the data rule: a lower bound on
  the number of conduction channels the sweep requires, and the effective
  density and mobility of each. Under the peaks rule: a fit at the count the
  peak finder chose, and whether its parameters are determined.

### 4.2 What the spectrum supplies to the data rule

- **FR-082** The mobility window shall be taken **per carrier type**, from the
  lowest and highest peak of that type, and never per peak. Research 004
  section 3.1 measures a per-peak window raising the residual from `0.043` to
  `1.59` on the same sweep, because binding each carrier to its own peak
  assumes the count the search exists to vary. *Amended 2026-09-15:* the peak
  count bounds the first search and is not a ceiling on the answer. Past it the
  count shall grow one step at a time — one more carrier of either sign, or
  both — for as long as FR-085 selects the larger combination, without a
  window, and never beyond a declared number per sign; an answer chosen past
  the bound shall say so. Research 004 section 6.2 measures the spectrum
  proposing one carrier of each sign at 70 to 90 K, where `2h+2e` fits `2.5` to
  `5` times better and reproduces.
- **FR-083** Starting points shall be taken from the spectrum's **distribution**
  and not from its peak list: the branch is divided into as many equal-weight
  segments as there are carriers of that type, and each segment's
  conductivity-weighted centre is one starting point. Research 004 section 3.2
  measures the peak list giving `0.427` against `0.043` when the requested
  count is smaller than the number of peaks, because the multi-start of
  feature 001 perturbs around its starting point rather than sampling the
  declared bounds.

### 4.3 Selecting a combination

- **FR-084** Every combination up to the bound shall be fitted and recorded.
  The program shall not stop at the first acceptable one.
- **FR-085** A combination shall be selected only if it passes all of:
  fitting the data to within the declared factor of the best any
  **reproducible** combination achieved; reproducing across starting points,
  judged on the starting points that finished and never on how long the fit
  took; every carrier carrying at
  least the declared share of the conduction; and no carrier resting on a
  declared bound. **Fit quality is the first of these and is not tradeable:**
  a combination that does not describe the data is not a candidate however
  well determined it is. Where a combination that does not reproduce fits
  better than the selected one by more than the declared factor, the program
  shall report that combination and by how much, beside the verdict: the data
  asks for more freedom than it determines, and a selection that passes must
  not hide it.
- **FR-086** Where no combination passes, the program shall say so, name the
  closest one and name the tests it failed. It shall not select by relaxing a
  test.
- **FR-087** The selected combination shall be **graded** by the conditioning
  of its fit, and the grade shall be reported with the parameters. The
  conditioning shall **not** be a gate. Research 001 section 4.6 calibrated its
  threshold between "every parameter to `0.1 %`" and "a density wrong by
  `35 %`"; it separates trusting the digits from not, and gating on it discards
  answers whose trends are sound. *Amended 2026-09-15:* the grade says whether
  the parameters are determined and nothing about whether the curve is
  followed, so every answer shall also report its residual as a multiple of the
  measurement noise of each channel and the runs test of that residual, before
  the coefficient of determination. Research 004 section 6.2 measures the grade
  and the residual ranking the sweeps above 60 K in opposite orders, and the
  coefficient of determination ranking a sweep of `0.24 %` magnetoresistance
  followed to `7` times the noise below one missed by `53` times.

### 4.4 Finishing

- **FR-088** Every fit shall carry a wall-clock budget, and a fit that exceeds
  it shall be abandoned and recorded as cut short. Exceeding the budget shall
  not by itself decide any gate: whether a combination reproduces shall be
  decided by the spread of the starting points that finished. A spread
  measured across fewer than two finished starting points shall count as
  unmeasured, and an unmeasured spread is not a small one. The earlier form of
  this requirement made the clock a gate, on the measured claim that every fit
  over the budget also failed on its own merits; constraint C18 records the
  counter-example that withdrew it, in which the same combination reaching the
  same residual was kept on one machine and discarded on a slower one.
- **FR-089** Resampling shall be **opt in, per temperature**, and shall never
  run by default. Research 004 section 2 measures it at roughly `200` seconds
  per sweep against roughly `1` second for the selected fit.

### 4.5 Holding the model fixed across temperature

- **FR-090** The reader shall be able to fix the combination across a range of
  temperatures rather than letting each choose its own, and the program shall
  report what fixing it cost in residual at each temperature. A series whose
  model changes underneath it is not a series: `n(T)` cannot be plotted from
  fits that do not share a carrier set. The program shall also point out,
  unasked, a sweep carrying **more** carriers than a count that **both** of its
  neighbours share, and report what holding that sweep to their count would
  cost in residual. It shall not change the verdict on that account. Two
  conditions, each for its own reason: where the neighbours differ from each
  other the sweep sits inside a transition, which the count must stay free to
  follow; and freedom appearing at one temperature and gone on either side
  claims a carrier that exists only there, where a sweep carrying fewer
  carriers than its neighbours claims nothing. Telling a transition from an
  artefact is the reader's judgement and not the program's, and the program's
  part is to put the number in front of them.

### 4.6 What the reader receives

- **FR-091** A run under either count rule shall write, beside the files features 001 to
  003 already write, one table with a row per temperature -- count rule, combination,
  grade, both coefficients of determination, condition number, spread, the
  gates failed and the carriers that left the window -- one table with a row
  per fitted carrier, and one table with a row per combination tried. The
  combination table is what makes FR-084 checkable by the reader rather than
  asserted by the program.
- **FR-092** A run shall write one self-contained report page that opens in a
  browser with no network connection: the verdict per temperature first, then
  the measurement against the fit, then the parameters against temperature.
  **The verdict comes before the numbers**, because a reader shown the numbers
  first does not read the verdict, and in this program the verdict is often
  the finding. No script, style or font shall be fetched from anywhere.

---

## 5. Numerical requirements

- **NR-012** The wall-clock budget of FR-088 shall be enforced inside the
  residual evaluation, so that a fit is abandoned while it is running rather
  than after it returns. A budget that only checks between fits does not bound
  anything.

---

## 6. Physical model contract

No change. Both rules end in the model of PM-001 through a least-squares fit.
They differ only in what sets the number of carriers: the data, through
FR-085, or the spectrum's peak finder.

---

## 7. Acceptance criteria

| ID | Criterion | Default |
| --- | --- | --- |
| AC-026 | Residual of a candidate, as a multiple of the best any reproducible combination achieved, to count as fitting — equivalently, what one added carrier must buy | `2` |
| AC-027 | Spread across starting points, above which a combination is not reproducible | `0.01` |
| AC-028 | Share of the zero-field conduction below which a carrier has not earned its place | `0.001` |
| AC-029 | Wall clock a single fit is allowed, in seconds | `30` |
| AC-030 | Width of the mobility window, as a factor either side of the extreme peaks | `3` |

**AC-031.** Grades, by the condition number of the selected fit:
`A` at or below `1e3`, parameters determined; `B` to `1e4`, trends usable and
digits not; `C` to `1e6`, shape only; `D` above, not determined.

**AC-032.** On the 5 K sweep of the fixture the tests carry, the data rule
shall select `3h + 2e` at grade `A` and reproduce `R^2 = 0.999995` on the
longitudinal channel and `0.999992` on the Hall channel. This is the round
trip for this feature. It was first set on a sample's sweep, whose numbers are
in research 004 and are not published with the program; the fixture that
replaced it is generated from three carriers of each sign, so a five-carrier
answer is the right one.

---

## 8. Out of scope

- **Deciding how many carriers a sample has.** Transport alone cannot. The
  spectrum's peak count is an upper limit on the channels a sweep resolves and
  is not a band count — one non-circular orbit reads as three peaks (research
  003 section 7) — and the data rule's count is a lower limit on the channels a
  sweep requires. The number of Fermi pockets needs evidence this program does
  not take, such as quantum oscillations; a reader who has it holds the count,
  by FR-090 or by the peaks rule.
- **Deciding the carrier count without a reader.** FR-076 of feature 003 still
  holds. What this feature adds is a proposal with the evidence beside it.
- **Cancelling a running analysis.** The command line runs to completion. A
  reader who wants to stop one stops the process.

---

## 9. Deliberately excluded from this version

- **An information criterion over the combinations.** AIC and its relatives
  trade residual against parameter count on the assumption that the residual is
  noise. Research 003 section 6.1 measures a `4.7 %` residual floor that no
  Drude model reaches, so that assumption is known to be false here, and a
  criterion built on it would have chosen confidently and wrongly.
- **Automatic symmetrisation of raw data.** FR-008 and FR-009 already do it on
  request and stay off by default. A program that quietly replaces the
  measurement with its even and odd parts has changed the data without being
  asked.
