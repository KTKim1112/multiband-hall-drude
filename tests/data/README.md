# Reference data

The tests fit against `synthetic_5K.csv`, `synthetic_20K.csv`,
`synthetic_40K.csv` and `synthetic_series.csv`, which `make_synthetic.py`
writes. Run it from the repository root to reproduce them byte for byte:

    python tests/data/make_synthetic.py

Every number in the file is invented. Nothing here is a measurement, which is
why the fixture can be published with the program while a sample's sweeps
cannot.

## What it is, and why it is shaped this way

Six carriers, three of each sign, on the field axis of a real instrument: 361
records from -9 to +9 T at 0.05 T. The four-carrier configurations in
`configs/` fit it with **two** of each sign, and the band they cannot hold is
what gives the residual its structure. That matters: half of what these tests
check is what the program does when the model does not describe the data, and
a sweep generated from the model being fitted has no residual but the noise.

Measured on the fixture, at 5 K:

| fitted as | residual | R² | condition |
| --- | --- | --- | --- |
| `2h+2e` | `31.6` x noise | `0.998146` | `176` |
| `3h+3e` | `0.9` x noise | `0.999998` | `8332` |

The `3h+3e` row is the point of the design: a fit at the generating count
recovers every parameter to better than `0.4 %`, so the fixture has a known
answer. No measured sweep does.

Reproduced from a real semimetal, because tests depend on each of these:

- two carriers of each sign dominate, one fast and one slow, close to
  compensated, with a hole excess of `+2.1 %` at 5 K;
- the Hall channel changes sign between 20 K and 40 K -- the low-field slope
  is `+0.0282`, `+0.0111` and `-0.0705` micro-ohm cm / T -- so 40 K is
  electron dominated where the other two are hole dominated;
- the conditioning collapses at 40 K, `176`, `234`, `1099`, because the two
  electron bands there sit close enough in mobility that four carriers cannot
  separate them;
- exactly one carrier of the 5 K fit has `mu B` below 1 at 9 T, at `0.92`;
- exactly one parameter jumps between neighbouring temperatures, a density,
  by `7.0` across 20 to 40 K, while nothing moves by more than `1.4` across
  5 to 20 K;
- noise, symmetrised as the instrument's sweeps arrive: the longitudinal
  channel even in field, the Hall channel odd. A perfectly smooth sweep has a
  second difference of zero, and the residual-over-noise axis of FR-087
  divides by it.

## The measured sweeps this replaced

`csv3sb5_5K.csv`, `csv3sb5_20K.csv`, `csv3sb5_40K.csv` and
`csv3sb5_series.csv` were derived from files supplied by the maintainer on
2026-08-26 and 2026-08-27: CsV3Sb5, current in the `ab` plane, field along
`c`. They are a sample's measurements and are not published with the program.

Where a test recorded a number from them, that number was re-recorded on the
synthetic fixture and the test says so. The research documents keep the
measured values and the claims made with them; those claims are about the
sample and are not restated by any test here.
