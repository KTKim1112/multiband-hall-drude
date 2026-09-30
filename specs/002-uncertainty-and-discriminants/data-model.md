# Data model 002 — what feature 002 adds to the configuration, codes and output

> English is normative. `docs/002-data-model.ko.md` is its translation.
>
> This document extends `specs/001-multiband-drude/data-model.md`. Nothing
> declared there changes. A reader who has the feature 001 document does not
> have to re-read it: everything below is new.

---

## 1. Configuration

A new section, inert by default in the sense of feature 001: a configuration
that does not mention it behaves exactly as it did before, except that the
discriminants of section 4.2 of `spec.md` are cheap enough to run always.

```text
uncertainty
  enabled              false      resampling is work, and it is opt-in
  resamples            200        AC-011
  block_length         20         AC-012, recorded with the result by FR-059
  interval_fraction    0.68       AC-013
  seed                 null       null means derived from the run seed
```

```text
discriminants
  harmonic_tolerance   0.05       AC-014
  parity_threshold     0.02       AC-015
```

`uncertainty.enabled` defaults to false because a resampling run costs
`resamples` fits per temperature, and feature 001's contract is that a default
run does the cheapest honest thing. Everything else here is a threshold, and
thresholds are inert by construction: they decide what is *reported*, never
what is *fitted*.

---

## 2. Diagnostic codes

| Code | Raised when | Source |
| --- | --- | --- |
| `D_HARMONIC_LADDER` | The fitted mobilities satisfy all three ladder conditions, so the carrier set may be one non-circular orbit rather than several bands | FR-063 |
| `D_PARITY_VIOLATION` | A channel carries wrong-parity content above `discriminants.parity_threshold`, measured before symmetrisation | FR-065, AC-015 |
| `D_SINGLE_POLARITY` | The sweep carries one field polarity, so the parity violation could not be measured and any channel admixture remains | FR-066 |
| `D_INTERVAL_LOWER_BOUND` | A resampling interval was computed for a fit whose residual is structured, so the interval understates the uncertainty | FR-060 |

`D_HARMONIC_LADDER` is a warning and not an error. A ladder does not prove one
orbit; it says the data cannot distinguish that reading from the multiband one,
which is a different and weaker statement, and the report carries the three
conditions separately so a reader can see which held.

---

## 3. Output files

| File | One row per | Carries |
| --- | --- | --- |
| `uncertainty_<T>K.csv` | parameter | value, lower and upper bound of the interval, one-sigma, whether the interval is a lower bound |
| `correlation_<T>K.csv` | parameter | correlation with every other parameter |
| `derived_vs_T.csv` | temperature | total density of each sign, their ratio, their difference, each with its interval |
| `harmonics_vs_T.csv` | temperature | each channel's ratio to the fastest, its nearest harmonic, and which of the three conditions held |

`resolved_config.json` gains the `uncertainty` and `discriminants` sections,
including the block length and resample count actually in force, so that
FR-037 continues to hold: feeding the emitted configuration back reproduces
the run, intervals included.

---

## 4. Report text

Two sentences are emitted on every run, whatever the outcome.

- FR-064, always: a fitted mobility is an **effective channel mobility**, not
  the microscopic mobility of a Fermi pocket.
- FR-060, whenever an interval accompanies a structured residual: the interval
  covers resampling of the residual and **not** the misspecification that made
  the residual structured, and is therefore a lower bound.

Both live in the presentation layer with the rest of the Korean wording, per
Article IV and Article VIII.
