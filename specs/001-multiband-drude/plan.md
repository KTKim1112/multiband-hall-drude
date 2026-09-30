# Plan — with what technology, and how

Feature 001 · 2026-08-26

`spec.md` says what is built and names no technology. This document names all
of it, and nothing here reopens what is being built.

---

## 1. Technology, and why each

| Choice | Why | Article IX justification |
| --- | --- | --- |
| Python 3.12 | Already installed; the ecosystem below is where numerical physics work lives | none needed |
| `numpy` | Array arithmetic. The only dependency the physics core is allowed | Article I |
| `scipy.optimize.least_squares` | Trust-region least squares taking a residual vector, with box bounds and a selectable robust loss — the three things FR-014, FR-035 and FR-025 require together. See research 5.2 | none needed |
| `pandas` | Reading the data table and writing the output tables. Confined to two modules | Confinement is the justification; see 2.2 |
| `matplotlib` | Figures (FR-041) | none needed |
| `pytest` | Tests | none needed |
| JSON for the configuration | No dependency, editable by hand, and exact round trip so FR-037 reproduces a run | Considered YAML; rejected under Article IX as a dependency bought for comment syntax |
| CSV for the outputs | Opens in Origin, Igor, Excel and every plotting tool the maintainer already uses | none needed |

Nothing else is added without amending this table.

---

## 2. Module layout

### 2.1 The physics core — `mbfit/core/`

Article I: these modules import `numpy` and the standard library, nothing else.
No file access, no argument parsing, no tables, no plots.

| Module | Holds | Requirements |
| --- | --- | --- |
| `constants.py` | the elementary charge | research 1 |
| `units.py` | every conversion between boundary units and SI, and nowhere else | NR-004, Article V |
| `drude.py` | conductivity tensor, resistivity inversion, and the reverse | PM-001, PM-002 |
| `canonical.py` | ordering carriers by decreasing mobility within each sign, and detecting that the order changed | PM-003, FR-047 |
| `metrics.py` | coefficient of determination, RMSE, robust channel scale, runs-test score over the field-ordered residual | FR-020, FR-040, AC-007 |
| `residual.py` | assembling the residual vector: which records are admitted, channel selection, space selection, normalisation, weights, low-field emphasis | FR-018 to FR-022, FR-049 |
| `penalties.py` | temperature coupling and monotonic penalties, applied to canonically ordered carriers and cut at declared breaks | FR-027 to FR-032, FR-052, FR-053, NR-003 |
| `errors.py` | the exception type carrying a code | Article IV |

The core knows nothing about temperatures being read from a file, or about
there being a file at all. It takes arrays and returns arrays. This is what
makes AC-008, the round trip, testable without any I/O.

### 2.2 Everything else — `mbfit/`

| Module | Holds | May import |
| --- | --- | --- |
| `config.py` | schema, defaults, validation, `ResolvedConfig` | core |
| `dataio.py` | reading the data set, preprocessing, grouping by temperature | core, `pandas` |
| `fitting.py` | the three strategies, multistart, the log-space parameter vector, the singular values of the converged derivative | core, `scipy` |
| `diagnostics.py` | the `D_*` rules | core |
| `report.py` | writing the output files and figures | core, `pandas`, `matplotlib` |
| `messages.py` | Korean wording, keyed by error and diagnostic code | nothing |
| `cli.py` | the command line, the `--no-priors` switch of FR-057, and the only place a sentence is shown | everything |

`pandas` appears in `dataio.py` and `report.py` only — at the two boundaries
where a table is read and written. Between them everything is a `numpy` array
or a plain structure. The justification Article IX asks for: `pandas` group-by
and CSV handling are worth their weight at the boundary, and are a liability
in the middle, where they would hide array shapes behind labels.

### 2.3 Tests — `tests/`

| File | Enforces |
| --- | --- |
| `test_core_purity.py` | Article I, by parsing the imports of every module in `core/` |
| `test_ascii.py` | Article IV, by rejecting non-ASCII outside `messages.py` and `cli.py` |
| `test_units.py` | NR-004, each conversion and its inverse |
| `test_drude_known.py` | K1 to K8 of research 2.3 |
| `test_canonical.py` | PM-003, FR-047 |
| `test_residual.py` | FR-018 to FR-022 |
| `test_penalties.py` | FR-027 to FR-032, FR-052, FR-053, including FR-031 on uneven spacing |
| `test_config.py` | every `E_CONFIG_*` code |
| `test_dataio.py` | every `E_DATA_*` code, FR-005, FR-007 to FR-010 |
| `test_roundtrip.py` | **AC-008** |
| `test_strategies.py` | FR-023 to FR-026 |
| `test_diagnostics.py` | every `D_*` code |
| `test_legacy_agreement.py` | that the new code reproduces `legacy/` numbers, with the sign of `rho_xy` deliberately inverted — see 4 |
| `test_cli.py` | end to end on `example_input.csv` |

---

## 3. The parameter vector

One place decides how carriers become a vector, and both `fitting.py`
strategies use it.

```text
single temperature:   [log n_1, log mu_1, log n_2, log mu_2, ...]
global strategy:      the above, concatenated over temperatures in
                      ascending order, so temperature i occupies
                      the slice [i*2N : (i+1)*2N]
```

Log space is NR-002. Bounds are the logarithms of the declared bounds. On
output, a component within floating-point distance of a log-bound is replaced
by the declared bound itself, which is NR-006.

The global strategy has `2 N n_T` parameters; for four carriers and twenty
temperatures that is 160, well within what a trust-region method with a
finite-difference Jacobian handles, at the cost of `161` model evaluations per
Jacobian.

---

## 4. What to do with `legacy/`

The prototype in `legacy/` is an answer key with one known defect: the Hall
sign (research 2.1). `test_legacy_agreement.py` runs it for real and requires
the new code to reproduce

- `rho_xx` to `1e-12` relative, unchanged;
- `rho_xy` to `1e-12` relative **after negation**.

This pins the correction as a deliberate, single, documented sign change,
rather than leaving open the possibility that something else also moved. The
test is deleted when the legacy file is, and not before.

The prototype cannot currently be run end to end: the configuration document
`README_KR.md` refers to was never delivered. Only its functions are used.

---

## 5. Order of construction

Bottom up, so that each layer is tested against known answers before anything
depends on it. Detailed in `tasks.md`. The essential constraint is that
**`test_roundtrip.py` passes before any strategy, diagnostic or output exists**,
because every later result is meaningless if it does not.

---

## 6. Deliberately not built

- No analytic Jacobian (research 5.2).
- No parallelism. Measure first.

### 6.1 Reversed on 2026-09-15: a web layer, a server, and a packaged build

This section originally also read *"No graphical interface, no web layer, no
server"* and *"No packaging or installation beyond running from the
repository"*, on the grounds that the maintainer runs a command and reads CSV
files. Both were right for a maintainer and are wrong for the audience the
program now has. Article IX requires the justification for a dependency to be
written here before the dependency is added, so it is.

**What changed.** The maintainer decided to hand the program to colleagues who
have no Python, no Node and no administrator rights. For them a command line
and a folder of CSV files is not a program. The sibling project
`nodeless-sc-gap` has already paid for the route that works for that audience
and recorded its costs: a local web page served by a Python process frozen into
one Windows folder.

**What is added, and why each is the simplest thing that does the job.**

| Dependency | Why nothing smaller works |
| --- | --- |
| `fastapi` | Validates request bodies and serialises results; the alternative is hand-writing both, which is more code and more bugs |
| `uvicorn` | The server `fastapi` runs under. Loopback only, one user |
| `python-multipart` | Required by `fastapi` to accept uploaded files |
| `pyinstaller` | Freezes Python, numpy and scipy into a folder a recipient can run |
| a Vite + React frontend, built at package time | The screen has to show a verdict per temperature with its evidence, a column mapping, and a long job with progress. A static page cannot hold that state honestly |

**What is kept out, deliberately.**

- **The web layer lives outside `mbfit/`**, in `app/` and `frontend/`. The
  library keeps Article I and Article IV untouched: `mbfit/` still imports no
  web framework and still contains no Korean outside `cli.py` and
  `messages.py`. The server is a presentation layer like the command line.
- **No database, no queue, no accounts.** One user on one machine; a job lives
  in a dictionary and is forgotten on restart, as in `nodeless-sc-gap`.
- **The command line stays first.** Everything the page does is reachable
  without it, and the tests keep running against the library.

**One-folder, not one-file.** Measured in `nodeless-sc-gap`: a one-file build
unpacks 54 MB into a temporary directory on every launch, starts in 12.6 s
against 5.0 s, and trips antivirus heuristics because that is the shape of a
dropper. The one-folder build is zipped for sending.
