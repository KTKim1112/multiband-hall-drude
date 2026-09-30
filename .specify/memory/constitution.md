# Constitution — Multiband Hall / Drude Analysis

Version 1.0.0 · Ratified 2026-08-26

These are the rules this project does not break. Breaking one requires
amending this document first, in its own commit, with the reason recorded.

---

## Article I — The physics core depends on nothing but arrays

Every module under `mbfit/core/` may import `numpy` and the Python standard
library, and nothing else. No `pandas`, no `scipy`, no `matplotlib`, no file
access, no argument parsing.

**Why.** The Drude conductivity tensor and the resistivity inversion are the
part of this program that must still be correct in ten years. Fitting
libraries, table libraries and plotting libraries change. Keeping the core
free of them means the physics can be tested with no I/O, read without
following an import trail, and reused from any other program.

**Enforced by** `tests/test_core_purity.py`, which parses the imports of every
module under `mbfit/core/` and fails if a forbidden name appears.

---

## Article II — No physical quantity without a test against a known answer

No function that computes a physical quantity is written without a test
comparing it to an independently known result: a closed-form limit, an
analytic special case, or a published number.

**Why.** This project already produced the failure this article exists to
prevent. The inherited prototype reproduced `rho_xx = 1 / (n e mu)` exactly
while returning `rho_xy` with the wrong sign. Nothing crashed. R-squared was
unaffected. Only the electron/hole conclusion was wrong. A wrong fit does not
crash — it returns a plausible number, and no amount of reading catches that.

The minimum set of known answers is listed in `research.md` section 2.

---

## Article III — Specification precedes implementation

Code follows the specification. When the specification turns out to be wrong,
**the specification is corrected first**, in its own commit, with the evidence
recorded in `research.md`; only then is the code changed.

**Why.** If implementation leads, the document becomes a lie at that moment,
and from then on nobody can say which of the two is right.

---

## Article IV — The library returns codes, not sentences

Functions under `mbfit/` signal failure by raising an exception carrying a
stable machine-readable code (`E_CONFIG_*`, `E_DATA_*`, `E_FIT_*`) listed in
`data-model.md`. Human-facing wording — including all Korean — lives only in
the presentation layer (`mbfit/cli.py` and its message table).

**Why.** Keeps the diagnosis testable: a test asserts on `E_DATA_MISSING_COLUMN`,
not on a sentence that changes whenever the wording is improved. It also keeps
non-ASCII text out of the computational source.

**Enforced by** `tests/test_error_codes.py`, which fails if any module outside
the presentation layer contains a non-ASCII character.

---

## Article V — SI inside the core; non-SI values name their unit

Inside `mbfit/core/` every quantity is SI. Any variable holding a non-SI value
carries the unit in its name: `n_cm3`, `mu_cm2Vs`, `rho_uohmcm`. Conversion
happens at exactly one place, `mbfit/core/units.py`, and nowhere else.

**Why.** Unit confusion is the first cause of silent error in physics code.
This program mixes cm^-3, cm^2/(V s), micro-ohm cm and S/m in a single
expression; a factor of 1e6 or 1e8 misplaced changes a carrier density by
orders of magnitude without changing the shape of any curve.

---

## Article VI — A result travels with its assumptions and its violations

A fit result is never a bare set of numbers. It carries the configuration that
produced it, the seed used, the fit quality, and every diagnostic violation
detected (parameter pinned to a bound, jump between adjacent temperatures,
systematic residual structure, non-unique solution).

**Why.** The classical independent-carrier Drude model returns a number for
data that breaks every one of its assumptions. A high R-squared is not
evidence that the carrier decomposition is unique. The warnings must arrive
attached to the answer, not in a log the user does not read.

---

## Article VII — A stochastic computation takes a seed and reports it

Multistart, bootstrap, and any other randomised procedure accept an explicit
seed and record in their output the seed actually used. Two runs of the same
configuration produce identical numbers.

**Why.** A carrier density that changes between runs cannot be cited.

---

## Article VIII — English in the repository, the reader's language on screen

Source, documents, and commit messages are written in English. Text shown to
the user is Korean by default, and may be English where the reader chooses it.
Each language's sentences live in one place and nowhere else, so that a
sentence written into a component is a sentence the other language does not
have. Teaching material under `docs/` is exempt and may be written in Korean.

---

## Article IX — Simplicity is the default

The simplest thing that satisfies the specification is chosen. Any added
complexity — a dependency, an abstraction layer, a configuration option —
requires a written justification in `plan.md`.

**Why.** The maintainer is a researcher, not a full-time engineer.

---

## Article X — Every fitting constraint records its five answers

Adding any constraint, prior, penalty or bound that influences the fitted
parameters requires answering, in writing, in `research.md`:

1. Why is it needed?
2. Is it a hard constraint or a soft prior?
3. What data or external measurement is the evidence for it?
4. How much does it change the fit quality?
5. Does the conclusion survive removing it?

**Why.** This is inherited verbatim from the received specification
(`SDD_SPEC_KR.md` section 9) and is the central rule of this project. A
multiband fit can be made to look good by adding physically arbitrary
constraints. This article is what prevents that from happening quietly.
