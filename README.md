# mbfit — multiband magnetotransport analysis

Takes `rho_xx(B)` and `rho_xy(B)` measured at one or more temperatures and
returns how many conduction channels of each sign the data requires, the
effective density and mobility of each, and — before any of those numbers —
how well the curves are followed and whether the numbers are determined.

**Where this matters.** A single-field Hall measurement gives one carrier
density and one mobility, and those are the right numbers only when one carrier
carries the current. Where two or more do — a doped layer beside its substrate,
a two-dimensional gas beside a parallel path, a compensated or narrow-gap
semiconductor, a film whose surface conducts — the single-field numbers are a
weighted average of channels that may not even share a sign, and they move with
field without anything about the sample having changed. Separating them is what
multicarrier analysis of the field sweep is for, and it is why the method's own
literature, cited at the end, is largely semiconductor characterisation.

The hard part is not the fitting. A four-carrier model will follow almost any
smooth pair of curves, so a good fit is not evidence that the densities and
mobilities behind it mean anything. On a synthetic sweep built from known
carriers — the only kind where the error can be known at all — this program's
own calibration found an `R^2` of `0.99959` alongside a low-mobility density
wrong by `35 %`. Nothing in the fit quality says so.

That is what the program is built around. It reports what the measurement
determines before it reports what it fitted, grades the conditioning, and
refuses rather than guesses.

![The verdict table: three temperatures whose fits all reach an R-squared of
1.0000, graded A, C and B](docs/images/verdicts.png)

Three sweeps of the test fixture, analysed. Every one is followed to an `R^2`
of `1.0000` — and the grades are `A`, `C` and `B`, because the conditioning
behind those identical curves differs by sixty times. The 20 K row is the one
worth looking at: a perfect-looking fit whose carrier numbers are shape only. A
tool that reported the parameters and stopped would have said nothing was wrong.

## Download

**No Python, no Node, no administrator rights.** From
[the latest release](../../releases/latest), take the file named

> **`MultibandHall-windows.zip`** — about **64 MB**

and not either of the two below it. GitHub adds `multiband-hall-drude-<tag>.zip`
and `.tar.gz` to every release by itself; those are the source code, about
0.6 MB, and hold no program at all. The size tells them apart at a glance.

Unzip it anywhere, open the `MultibandHall` folder inside, and double-click
`MultibandHall.exe` — it is one level down, beside a folder called `_internal`:

```text
MultibandHall-windows.zip
└── MultibandHall\
    ├── MultibandHall.exe      <- double-click this
    └── _internal\             <- the Python runtime; leave it alone
```

A console window opens and then your browser, on the analysis page. Closing the
console stops the program. Nothing is installed and nothing leaves the machine:
the server listens on the loopback interface only.

Windows may warn that the program is unsigned, because it is. Some antivirus
software quarantines unsigned executables of this kind; if the exe is missing
after unzipping, look in the quarantine before concluding the download failed.

Running from source, or from the command line, is described under
[Running it](#running-it).

---

The Korean guide is [`docs/README.ko.md`](docs/README.ko.md). The documents
under `specs/` are normative; those under `docs/` are their translations.

**One document set is missing here on purpose.** Each feature has a `research`
document recording what every threshold and default in this program was
calibrated against, and that calibration was measured on a sample whose data is
not published. Those documents are therefore not published either. The rest
cites them -- "research 4.6 measured" -- and the citations are left standing so
that what settled what is still visible. Ask the maintainer for a number you
need from them.

---

## What transport alone can and cannot tell you

Magnetotransport sees conduction channels, not Fermi pockets. This program is
built around the two limits that follows from that:

- **An upper bound from the mobility spectrum.** The spectrum's peak count is
  roughly how many channels the sweep resolves. It is not a band count — one
  non-circular orbit reads as three peaks (research 003 section 7) — and near a
  transition peaks can merge and read too few.
- **A lower bound from the fit.** The data rule returns the smallest set of
  channels the sweep requires: fewer fail to describe it. Each channel's
  density and mobility are *effective* values, and a channel may be several
  pockets that transport cannot tell apart.
- **The number of pockets needs evidence from outside transport** — quantum
  oscillations, band calculations. With it, hold the count; without it, the
  lower bound is what the data supports.

---

## The procedure

For each temperature:

1. **Mobility spectrum.** The spectrum sets, for holes and for electrons, an
   upper limit on the number of bands and the range of carrier density and
   mobility (the method of the literature below).
2. **Multiband fit.** Inside that range, combinations are fitted with a
   classical multiband Drude model of `rho_xx` and `rho_xy` together, and the
   smallest one that fits and gives the same answer from every starting point is
   kept.
3. **More bands only if clearly better.** If one more band cuts the residual by
   more than a factor of 2 and still reproduces, the count grows — past the
   spectrum's limit if need be — and the step repeats. Otherwise the answer is
   confirmed.

What the answer claims: the number of bands is a lower bound on the conduction
channels the sweep requires, and the densities and mobilities are effective
values of those channels.

Step 3 matters where the spectrum's peaks merge: approaching a transition they
can propose one band of each sign where two or three of each fit several times
better. Measured on a sample, and recorded in research 004 section 6.2, which
is not published with the program.

**Holding the count to the spectrum's peaks**, as the published procedure of
Liu et al. (Phys. Rev. Lett. 135, 056502, 2025) does, is available on the
command line as `--count peaks` for a reader whose count is supported by
evidence outside transport. On these sweeps it gives the same curves with
parameters that do not reproduce where the peaks propose too many, and misses
where they merge (research 004 section 4.2).

---

## Reading the verdict

Every temperature comes with, in this order:

- **Residual / noise**, for `rho_xx` and `rho_xy`: how well the curves are
  followed, on the scale of the measurement. No few-carrier model reaches the
  noise on these sweeps; compare across temperatures and combinations.
- **Grade** A to D, from the condition number of the fit: whether the
  densities and mobilities are determined. A curve can be followed closely
  with a C (little magnetoresistance) or missed with an A (a wrong model,
  firmly determined) — which is why both are shown.
- **Gates failed**: does not fit, not reproducible, a carrier doing no work, a
  carrier on a bound.
- **Warnings**: a larger combination that fits better but is not determined;
  an answer chosen past the spectrum's bound; carriers that left the window.
- **Island**: a sweep carrying more carriers than a count both of its
  neighbours share, and what holding it to theirs would cost in residual. It is
  reported and never acted on. A count must stay free to follow a real
  transition, and telling a transition from a fitting artefact is yours to do;
  the program's part is to put the number in front of you. To hold a band to
  one count — which is what `n(T)` needs, since it cannot be plotted across a
  model that changes underneath it — use the refit control on the page or
  `workflow.fixed_counts` on the command line.
- **Roughness of a band**: a band held to one count also reports how far its
  parameters are from varying smoothly with temperature, in the measure a
  smoothing penalty acts on (FR-027). You can then ask for that penalty at one
  of three strengths. None is free: smoothness is bought with residual, and the
  price is reported per temperature. A large price says the model changes across
  the band — a reason to divide the band, not to press harder. Measured on a
  sample: where the series was already smooth there was little to remove, and
  approaching a transition halving the curvature cost a multiple of the
  residual at the worst sweep. The numbers are in the research record.
- `R^2` is shown last. It measures residual against the curve's own variation
  and ranks sweeps with little magnetoresistance unfairly low.

---

## Running it

### The page, and the Windows folder

This is the route most readers want, and it is one download: the 64 MB
`MultibandHall-windows.zip` from [the latest release](../../releases/latest) --
not the source archives GitHub adds beside it -- unzipped, and
`MultibandHall\MultibandHall.exe` double-clicked. A console window opens and
then the browser; closing the console stops the program. No Python, no Node, no
administrator rights. The server listens on the loopback interface only, and
the files stay on the machine.

The zip is a build product and is not in the repository. Every release carries
one, and `.\packaging\build.ps1` makes the same folder from source (see the end
of this section).

![Uploading sweeps: each file listed with its row count and the temperature
read from its name](docs/images/upload.png)

Drop the files anywhere on the page — one temperature per file or several,
`rho_xx` and `rho_xy` together or in separate files — check the proposed
column mapping and units, and start. Excel files need saving as CSV first. Progress can be stopped, keeping the
temperatures that finished. A precise check — resampling for intervals — can be
run per temperature. The page is in Korean or English, chosen in the header and
remembered.

![The adjustment step: refit a chosen temperature at a carrier count you pick,
with the procedure's own verdict kept beside it](docs/images/adjust.png)

A finished analysis opens a sixth step, **Adjust and confirm**, for when the
procedure landed somewhere unphysical at one temperature or the series cannot
be read as one series. Adjustments accumulate a temperature at a time: each
covers the sweeps it names and leaves the rest as the procedure decided them,
so a series can be repaired piece by piece and undone piece by piece. Nothing
there erases the answer the procedure reached, which stays on the results step
and stays downloadable.

Confirming does not gather the numbers on the screen. It runs the procedure
again under the settings the adjustments amount to, so it takes minutes -- and
what that buys is that the tables you download describe one run throughout,
and that the configuration document included with them gives the same answer
on the command line:

```bash
python -m mbfit --config config.json --data combined.csv --out reproduced --count data
```

`--count data` names the rule the page ran. The document carries the
adjustments themselves -- the pinned counts and any coupling -- and the
procedure reads them from it. Both files are in the same zip.

`combined.csv` is your own sweeps gathered into one table, and the fitted
curve is written beside them: `rhoxx_fitted`, `rhoxy_fitted` and their
residuals, at the same field and temperature, with `in_fit_window` saying
which rows the fit used. `measured` there is the channel as the fit saw it,
which is the raw column unless symmetrising was asked for. The four declared
columns are untouched, which is why the same file still reproduces the run.

The adjustments themselves are three. Any temperature, or
any band of them, can be refitted at a carrier count you choose without running
the analysis again; the verdict the procedure reached stays beside it and the
price in residual is reported, so an override can be seen as well as made. A
band of three or more temperatures held to one count can also be coupled across
temperature at one of three strengths, with what each strength cost per
temperature; no strength is free, and a large price is a reason to divide the
band, not to press harder. And for each temperature the mobility spectrum that
bounded its search -- the distribution per carrier sign, the peaks found in it
and the window those became -- can be unfolded. Its vertical axis is a
normalised weight, not a carrier density.

From source: `pip install -r requirements.txt -r requirements-app.txt`,
`cd frontend && npm install && npm run build`, then `python -m app.desktop`.
Build the folder with `.\packaging\build.ps1`.

---

### Command line

```bash
python -m pip install -r requirements.txt
python -m mbfit --data tests/data/synthetic_series.csv \
                --config configs/synthetic_workflow.json \
                --out results --count data
```

`--count peaks` holds the count to the spectrum's peaks (command line only). Without `--count` the
program fits exactly the carriers the configuration declares. Open
`results/report.html` first.

`--symmetrize-rhoxx` and `--antisymmetrize-rhoxy` replace the data with its
even and odd parts in `B`; both are off unless given, and the parity violation
is measured before either replacement.

## What a run writes

| File | One row per |
| --- | --- |
| `report.html` | run — verdict per temperature, measurement against model, parameters against temperature, the spectrum that bounded each search, how far the band is from a smooth series, every combination tried; opens offline |
| `workflow_summary.csv` | temperature |
| `workflow_carriers.csv` | fitted carrier |
| `workflow_candidates.csv` | combination tried |

---

## References

The mobility spectrum and its use with multicarrier fitting:

- J. W. McClure, Phys. Rev. **112**, 715 (1958) — multicarrier galvanomagnetic analysis of graphite.
- W. A. Beck and J. R. Anderson, J. Appl. Phys. **62**, 541 (1987) — the mobility spectrum, as the maximum conductivity at each mobility.
- J. S. Kim, D. G. Seiler and W. F. Tseng, J. Appl. Phys. **73**, 8324 (1993) — multicarrier analysis of both tensor components normalised by `sigma_xx(0)`.
- J. Antoszewski, D. J. Seymour, L. Faraone, J. R. Meyer and C. A. Hoffman, J. Electron. Mater. **24**, 1255 (1995) — quantitative mobility spectrum analysis (QMSA).
- I. Vurgaftman, J. R. Meyer, C. A. Hoffman et al., J. Appl. Phys. **84**, 4966 (1998) — improved QMSA.
- J. R. Meyer, C. A. Hoffman, J. R. Ketterson, L. Faraone, J. Antoszewski and J. R. Lindemuth, J. Electron. Mater. **28**, 548 (1999) — QMSA for anisotropic bands.
- S. Kiatgamolchai et al., Phys. Rev. E **66**, 036705 (2002) — maximum-entropy mobility spectrum.
- D. Chrastina, J. P. Hague and D. R. Leadley, J. Appl. Phys. **94**, 6583 (2003) — Bryan's algorithm for the mobility spectrum.
- J. Antoszewski, G. A. Umana-Membreno and L. Faraone, J. Electron. Mater. **41**, 2816 (2012) — high-resolution mobility spectrum analysis.
- K. K. Huynh et al., New J. Phys. **16**, 093062 (2014) — mobility spectrum applied to a metal, Ba(FeAs)2.
- W. A. Beck, J. Appl. Phys. **129**, 165109 (2021) — general properties of mobility spectrum methods.
- I. I. Izhnin, K. D. Mynbaev, A. V. Voitsekhovskii and A. G. Korotaev, J. Appl. Phys. **132**, 155702 (2022) — discrete mobility spectrum analysis.
- S. Liu et al., Phys. Rev. Lett. **135**, 056502 (2025), and its Supplemental Material section III — the procedure the `peaks` rule follows.

---

## Layout

| Path | What |
| --- | --- |
| `mbfit/core/` | the physics: numpy and the standard library only |
| `mbfit/` | reading, fitting, spectrum, workflow, reports, command line |
| `app/` | the server behind the page; imports `mbfit`, never the reverse |
| `frontend/` | the page; every sentence on it is in `src/labels.ts` |
| `packaging/` | the Windows folder build |
| `specs/00N-*/` | specification, research, data model, tasks per feature |
| `docs/` | Korean translations and the walkthrough |
| `tests/` | `python -m pytest -q`; `-m slow` for the gates that need thousands of fits |

---

## Licence

MIT, in [`LICENSE`](LICENSE).

It covers this program. It does not cover the papers under **References**,
which are cited and not redistributed, nor any measurement you analyse with
it: no sweep of a sample is published here, and the fixtures under
`tests/data/` are synthetic.
