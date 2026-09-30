"""Generate the synthetic reference sweeps the tests fit against.

Run from the repository root:

    python tests/data/make_synthetic.py

The measured sweeps of a real sample cannot be published, so the tests run
against sweeps this file makes. The parameters below are invented round
numbers, fitted to nothing, and they are the truth a test may assert against:
no measured fixture in this repository has a known answer.

**Three carriers of each sign, fitted with two.** A sweep generated from the
model the tests fit with would have no residual but the noise, and half of
what these tests check is what the program does when the model does *not*
describe the data: a structured residual, an interval that must be read as a
lower bound (FR-060), a noise floor far below the residual, correlations
between parameters that are standing in for one another. Generating from six
carriers and fitting four reproduces all of it, with the cause known -- the
third band of each sign -- which is more than the measured sweeps offered.

A fit at 3h+3e still recovers the truth exactly, so the same fixture serves
the tests that check a fit finds what produced the data.

Also reproduced from a real semimetal, because tests depend on it:

- two carriers of each sign dominate, one fast and one slow, close to
  compensated;
- the Hall channel changes sign between 20 K and 40 K, so the low-field slope
  is positive at 5 and 20 K and negative at 40 K;
- noise. A perfectly smooth sweep has a second difference of zero, and the
  residual-over-noise axis of FR-087 divides by it.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

#: Field axis of the real instrument: -9 to +9 T in 0.05 T steps, 361 records.
FIELD_T = np.round(np.arange(-9.0, 9.0 + 1e-9, 0.05), 4)

#: Invented. `n` in cm^-3, `mu` in cm^2/Vs. The three mobilities of a sign are
#: a factor of about 6.5 apart, which is what makes the `_mid` band one that
#: two carriers cannot absorb: measured over that spread, a four-carrier fit
#: leaves `42` times the noise at 5 K against the `2.7` it leaves when the
#: bands are only a factor of 2.3 apart. The measured sweeps this fixture
#: replaces left `67` times the noise, so the character is the same.
TRUTH: dict[float, tuple[tuple[str, float, float, float], ...]] = {
    5.0: (
        ("h_fast", SIGN_HOLE, 5.0e20, 15000.0),
        ("h_mid", SIGN_HOLE, 1.1e21, 2300.0),
        ("h_slow", SIGN_HOLE, 2.3e21, 350.0),
        ("e_fast", SIGN_ELECTRON, 4.0e20, 18000.0),
        ("e_mid", SIGN_ELECTRON, 1.0e21, 1900.0),
        ("e_slow", SIGN_ELECTRON, 1.7e21, 300.0),
    ),
    20.0: (
        ("h_fast", SIGN_HOLE, 5.0e20, 9000.0),
        ("h_mid", SIGN_HOLE, 9.5e20, 1400.0),
        ("h_slow", SIGN_HOLE, 2.0e21, 210.0),
        ("e_fast", SIGN_ELECTRON, 4.2e20, 10000.0),
        ("e_mid", SIGN_ELECTRON, 9.5e20, 1230.0),
        ("e_slow", SIGN_ELECTRON, 1.9e21, 190.0),
    ),
    # 40 K is a different regime, as the sample this fixture replaces was: the
    # Hall channel has changed sign, the holes have become the minority, and
    # the two electron bands sit close enough in mobility that four carriers
    # cannot separate them. That is what makes the conditioning collapse here
    # and one density move by more than a factor of five from 20 K -- the jump
    # FR-047 has to find, and the ill-conditioned temperature AC-010 is about.
    40.0: (
        ("h_fast", SIGN_HOLE, 7.5e20, 3500.0),
        ("h_mid", SIGN_HOLE, 1.2e21, 600.0),
        ("h_slow", SIGN_HOLE, 2.5e21, 340.0),
        ("e_fast", SIGN_ELECTRON, 8.0e20, 4800.0),
        ("e_mid", SIGN_ELECTRON, 1.2e21, 3200.0),
        ("e_slow", SIGN_ELECTRON, 1.2e22, 150.0),
    ),
}

#: The quick fixture, for the command line's end-to-end tests and for the
#: quickstart: they exercise plumbing, and a three-second run says as much
#: about it as a three-minute one. Three temperatures, because a table and a
#: plot against temperature need more than one, and 49 records over a narrow
#: field range, because that is enough to fit two carriers.
#:
#: Two holes and one electron, declared and fitted as one of each. The same
#: reason as the larger fixture: a sweep the declared model describes exactly
#: leaves nothing for a diagnostic to report and nothing for a prior to move,
#: and two of these tests are about exactly those.
SMALL_FIELD_T = np.round(np.arange(-3.0, 3.0 + 1e-9, 0.125), 4)
SMALL: dict[float, tuple[tuple[str, float, float, float], ...]] = {
    5.0: (
        ("h1", SIGN_HOLE, 5.6e19, 7000.0),
        ("h2", SIGN_HOLE, 1.8e20, 600.0),
        ("e1", SIGN_ELECTRON, 5.5e19, 6800.0),
    ),
    10.0: (
        ("h1", SIGN_HOLE, 5.6e19, 6650.0),
        ("h2", SIGN_HOLE, 1.8e20, 570.0),
        ("e1", SIGN_ELECTRON, 5.5e19, 6460.0),
    ),
    20.0: (
        ("h1", SIGN_HOLE, 5.6e19, 6090.0),
        ("h2", SIGN_HOLE, 1.8e20, 522.0),
        ("e1", SIGN_ELECTRON, 5.5e19, 5920.0),
    ),
}
SMALL_NOISE = 3.0e-2

#: A folder of sweeps in the shape the instrument writes them, for the tests
#: that read uploads rather than fit them: three blank lines, a header naming
#: the channels but not the temperature, trailing empty columns, and the
#: temperature only in the file name. One file per temperature, and the table
#: of all of them that the command line reads, so that combining the one into
#: the other can be checked.
#:
#: The physics here is the simplest that will do -- one carrier of each sign,
#: mobility falling with temperature. These tests are about a reader.
UPLOAD_T_K = (5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 120.0)
UPLOAD_NOISE = 1.5e-3

#: Instrument noise, micro-ohm cm, one standard deviation. Of the order the
#: real sweeps show, so that the noise level FR-087 divides by is realistic.
NOISE_XX = 1.2e-3
NOISE_XY = 1.0e-3

#: Fixed, so the fixture is the same file on every machine and every run.
SEED = 20260920


def sweep(T_K: float, generator: np.random.Generator) -> np.ndarray:
    """One temperature, as `[T, B, rho_xx, rho_xy]` rows in the file's units."""
    carriers = TRUTH[T_K]
    n_per_m3 = np.array([n * 1e6 for _, _, n, _ in carriers])
    mu_m2Vs = np.array([mu * 1e-4 for _, _, _, mu in carriers])
    sign = np.array([s for _, s, _, _ in carriers])

    rho_xx_ohm_m, rho_xy_ohm_m = resistivity(FIELD_T, n_per_m3, mu_m2Vs, sign)
    rho_xx = rho_xx_ohm_m * 1e8                      # ohm m -> micro-ohm cm
    rho_xy = rho_xy_ohm_m * 1e8

    # The instrument's sweeps arrive already symmetrised -- the longitudinal
    # channel even in field, the Hall channel odd, to 0.0 -- so the fixture is
    # too. Noise that is neither sends the tests down code paths no measured
    # sweep reaches: NR-008 checks that resampling adds no symmetrisation of
    # its own by comparing a sweep with its symmetrised self, which is only
    # the same problem when the sweep was symmetric to begin with.
    noise_xx = generator.normal(0.0, NOISE_XX, rho_xx.shape)
    noise_xy = generator.normal(0.0, NOISE_XY, rho_xy.shape)
    rho_xx = rho_xx + 0.5 * (noise_xx + noise_xx[::-1])
    rho_xy = rho_xy + 0.5 * (noise_xy - noise_xy[::-1])
    return np.column_stack([np.full(FIELD_T.shape, T_K), FIELD_T, rho_xx, rho_xy])


def small_sweep(generator: np.random.Generator) -> np.ndarray:
    """The quick one: three temperatures, 49 records each, narrow field."""
    out = []
    for T_K in sorted(SMALL):
        carriers = SMALL[T_K]
        n_per_m3 = np.array([n * 1e6 for _, _, n, _ in carriers])
        mu_m2Vs = np.array([mu * 1e-4 for _, _, _, mu in carriers])
        sign = np.array([s for _, s, _, _ in carriers])

        xx_ohm_m, xy_ohm_m = resistivity(SMALL_FIELD_T, n_per_m3, mu_m2Vs, sign)
        xx, xy = xx_ohm_m * 1e8, xy_ohm_m * 1e8
        nx = generator.normal(0.0, SMALL_NOISE, xx.shape)
        ny = generator.normal(0.0, SMALL_NOISE, xy.shape)
        xx = xx + 0.5 * (nx + nx[::-1])
        xy = xy + 0.5 * (ny - ny[::-1])
        out.append(np.column_stack(
            [np.full(SMALL_FIELD_T.shape, T_K), SMALL_FIELD_T, xx, xy]))
    return np.vstack(out)


def write_uploads(generator: np.random.Generator) -> None:
    """One file per temperature as the instrument writes them, and their table."""
    folder = HERE / "uploads"
    folder.mkdir(exist_ok=True)
    combined = ["T(K),B(T),rhoxx(microohm cm),rhoxy(microohm cm)"]

    for T_K in UPLOAD_T_K:
        fall = (5.0 / T_K) ** 0.4                    # mobility falls with T
        n_per_m3 = np.array([8.0e19 * 1e6, 7.5e19 * 1e6])
        mu_m2Vs = np.array([9000.0 * fall * 1e-4, 8600.0 * fall * 1e-4])
        sign = np.array([SIGN_HOLE, SIGN_ELECTRON])

        xx_ohm_m, xy_ohm_m = resistivity(FIELD_T, n_per_m3, mu_m2Vs, sign)
        nx = generator.normal(0.0, UPLOAD_NOISE, FIELD_T.shape)
        ny = generator.normal(0.0, UPLOAD_NOISE, FIELD_T.shape)
        xx = np.round(xx_ohm_m * 1e8 + 0.5 * (nx + nx[::-1]), 5)
        xy = np.round(xy_ohm_m * 1e8 + 0.5 * (ny - ny[::-1]), 5)

        # Three blank lines, then the header, then the sweep -- and the
        # trailing empty columns the instrument leaves behind.
        lines = [",,,,,"] * 3
        lines.append("B_T,rho_xx_data_uohm_cm,rho_xy_data_uohm_cm,,,")
        lines += [f"{b:g},{a:g},{c:g},,," for b, a, c in zip(FIELD_T, xx, xy)]
        (folder / f"{T_K:g}K.csv").write_text("\n".join(lines) + "\n",
                                              encoding="utf-8", newline="\n")

        combined += [f"{T_K:g},{b:g},{a:g},{c:g}" for b, a, c in zip(FIELD_T, xx, xy)]

    (folder / "all_temperatures.csv").write_text("\n".join(combined) + "\n",
                                                 encoding="utf-8", newline="\n")
    print(f"  uploads/: {len(UPLOAD_T_K)} sweeps and their table")


def write(path: pathlib.Path, rows: np.ndarray) -> None:
    lines = ["T(K),B(T),rhoxx(microohm cm),rhoxy(microohm cm)"]
    lines += [f"{T:g},{B:g},{xx:.5f},{xy:.5f}" for T, B, xx, xy in rows]
    # Newline pinned, not left to the platform. `tests/data/README.md` says
    # this script reproduces the fixtures byte for byte, and `.gitattributes`
    # stores them with LF; on Windows the default would write CRLF and every
    # one of the eighteen would come back changed, which is how this was found.
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"  {path.name}: {len(rows)} records")


def describe(made: dict[float, np.ndarray]) -> None:
    """What the fixture is, in the terms the tests read it by."""
    from mbfit.config import resolve
    from mbfit.core.metrics import noise_second_difference
    from mbfit.dataio import load_dataset
    from mbfit.fitting import fit_dataset

    root = pathlib.Path(__file__).resolve().parents[2]
    for T_K, rows in made.items():
        low = np.abs(rows[:, 1]) <= 1.0
        slope = np.polyfit(rows[low, 1], rows[low, 3], 1)[0]
        noise = noise_second_difference(rows[:, 2])
        print(f"  {T_K:g} K: Hall slope {slope:+.4f} microohm cm / T, "
              f"noise {noise:.2e} microohm cm")

    import json
    for name, path in (("2h+2e", "synthetic_5K.json"), ("3h+3e", "synthetic_3h3e.json")):
        config_path = root / "configs" / path
        if not config_path.is_file():
            continue
        config = resolve(json.loads(config_path.read_text(encoding="utf-8")))
        dataset = load_dataset(HERE / "synthetic_5K.csv", config)
        fit = fit_dataset(dataset, config).fits[0]
        noise = noise_second_difference(dataset.groups[0].rhoxx_uohmcm)
        print(f"  5 K fitted as {name}: RMSE_xx {fit.rmse_rhoxx:.5f}, "
              f"{fit.rmse_rhoxx / noise:.1f} x noise, R2 {fit.r2_rhoxx:.6f}, "
              f"condition {fit.condition_number:.4g}")


def main() -> int:
    generator = np.random.default_rng(SEED)
    made = {T_K: sweep(T_K, generator) for T_K in sorted(TRUTH)}
    for T_K, rows in made.items():
        write(HERE / f"synthetic_{T_K:g}K.csv", rows)
    write(HERE / "synthetic_series.csv", np.vstack([made[T] for T in sorted(made)]))
    write(HERE / "synthetic_small.csv", small_sweep(generator))
    write_uploads(generator)
    describe(made)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
