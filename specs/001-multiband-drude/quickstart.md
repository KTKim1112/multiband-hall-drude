# Quickstart

Feature 001 · 2026-08-26

Written before the code exists, so it is also the specification of the command
line. Verified by running it at Gate 7 (T703).

---

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python -m mbfit --data tests/data/synthetic_5K.csv --config configs/synthetic_5K.json --out results
```

Three arguments, all required, and a fourth that is not: `--no-priors`. See
the workflow below. Nothing is written outside `--out`, and a test asserts
that.

Two configurations ship with the repository. `configs/synthetic_5K.json` is
two holes and two electrons for `tests/data/synthetic_5K.csv`, the sweep the
tests fit against. `configs/example_1e1h.json` is a small one-of-each fixture
for `tests/data/synthetic_small.csv`, useful for seeing the machinery run
quickly; it does not fit that data well, and the diagnostics say so, which is
itself worth looking at once.

Neither sweep is a measurement. `tests/data/make_synthetic.py` writes both and
`tests/data/README.md` says what they are and why they are shaped as they are.
A sample's sweeps are not published with this program.

## What comes back

```text
results/
  resolved_config.json        every setting used, and the seed
  diagnostics.csv             every warning, with its threshold and source
  fit_parameters_vs_T.csv     density and mobility per carrier, declared and
                              canonical order, per temperature
  fit_metrics_vs_T.csv        R-squared, RMSE, the conditioning of FR-055,
                              and the channel scales actually applied
  5K_fit.csv                  measured, fitted and residual at one
                              temperature, in both spaces, every record
                              including those outside the field window
  5K_rhoxx.png  5K_rhoxy.png
  multistart_5K.csv           every starting point and where it landed
  parameters_vs_T.png         only when there is more than one temperature
```

**Read `diagnostics.csv` before the parameters, and `D_ILL_CONDITIONED`
first of all** — it is the single line that says whether the data determined
the answer at all. A run can reach R-squared above 0.999 while a carrier
density is wrong by a third; research section 4.3 measured exactly that, and
section 4.6 shows the conditioning separating that case from a sound one by a
factor of thirteen. The diagnostics are what distinguishes the two.

## The smallest configuration that works

```json
{
  "schema_version": "1.0",
  "columns": {
    "T": "T(K)",
    "B": "B(T)",
    "rhoxx": "rhoxx(microohm cm)",
    "rhoxy": "rhoxy(microohm cm)"
  },
  "carriers": [
    {
      "name": "e1",
      "kind": "electron",
      "density":  {"init": 1e19, "min": 1e16, "max": 1e22},
      "mobility": {"init": 6000, "min": 1,    "max": 50000}
    },
    {
      "name": "h1",
      "kind": "hole",
      "density":  {"init": 1e19, "min": 1e16, "max": 1e22},
      "mobility": {"init": 6000, "min": 1,    "max": 50000}
    }
  ]
}
```

Everything else takes its default, and every default is inert: no coupling
between temperatures, no monotonic expectation, no low-field emphasis,
ordinary least squares, each temperature fitted independently. That is stage A
of the workflow below, and it is the honest place to start.

## The workflow

| Stage | Settings | What it is for |
| --- | --- | --- |
| A | defaults; `temperature_strategy: independent` | Find out what each temperature prefers on its own, with nothing imposed. The baseline every later result is compared against |
| B | `sequential` | Seed each temperature from the one below it and check that the solution continues rather than jumping. **Sequential does no smoothing.** It changes where the search starts, not what is minimised |
| C | `global_smooth`, `smoothing.order: 2`, coupling strengths above zero | The production fit, and the only mode in which a coupling penalty acts: one consistent parameter trajectory over the whole series. **Needs a long enough series** -- see the note below |
| D | run stage C again with `--no-priors`, then vary initial values, bounds, `fit_space`, `fit_mode`, coupling strength, `multi_start` | Find out which conclusions survive the settings, and which were settings |

> **Stage C needs four or five temperatures, and research 5.6 measures why.**
> A second-order penalty forms one curvature estimate from every three
> consecutive temperatures, so a three-temperature series gives a single
> interior node and the penalty has nothing to average over. Measured on the
> three sweeps of this project at 5, 20 and 40 K: at a coupling strong enough
> to change the answer, the well-conditioned 5 K sweep moved by `19 %` while
> the badly conditioned 40 K sweep it was meant to rescue moved by `65 %` and
> its `R2` fell. The penalty met them in the middle rather than lending the
> good one's information to the bad one. And a break placed at the obvious
> feature -- the Hall sign change between 20 and 40 K -- leaves segments of two
> and one temperature, neither able to carry a second-order term, so the
> penalty silently becomes nothing at all.
>
> With a short series, stop at stage B and report the independent fits. With a
> long one, raise the coupling from `0.01` and stop at the largest value that
> still leaves the well-conditioned temperatures inside the accuracy budget of
> research 4.8.

Stage D is not optional. Constitution Article X asks, of every constraint,
whether the conclusion survives its removal; stage D is where that is
answered, and `--no-priors` is the one-command form of the question:

```bash
python -m mbfit --data d.csv --config c.json --out results_nopriors --no-priors
```

Every soft prior off — coupling, monotonic expectation, low-field emphasis,
robust loss — and nothing else touched. Bounds and any field window stay, as
those declare the admissible domain rather than a preference within it. If the
carrier densities move materially between the two runs, the difference is the
prior speaking, not the data.

## Reproducing a run a year later

```bash
python -m mbfit --data tests/data/synthetic_small.csv --config results/resolved_config.json --out results_check
```

Every number identical. If they are not, that is a defect, not a property of
the method (NR-005).
