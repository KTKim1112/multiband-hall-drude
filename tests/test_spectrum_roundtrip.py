"""T1308 -- the round trip of FR-079, and why residual size cannot replace it.

Every other check this feature makes is internal: how well the extension
fitted, whether a plateau formed, whether the separated parts recombine. All
of them can pass while the carriers the spectrum finally reports fail to
describe the sweep they came from.

The two tests that matter here are the pair in the middle. One builds a sweep
the extension fits beautifully and whose carriers still fail to describe it,
which is what AC-025 is for. The other pins the explanation this project tried
first and had to withdraw, so that it is not reached for again.

The synthetic carrier sets are arbitrary, chosen for this project.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, diagnostics, fitting, spectrum
from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si, resistivity_from_si

FIELDS = np.round(np.linspace(-9.0, 9.0, 181), 6)

# three holes and three electrons, spread over a decade and a half
DENSITY = [2.6e19, 6.2e20, 1.5e21, 1.3e20, 3.3e20, 2.3e21]
MOBILITY = [50000.0, 15900.0, 1930.0, 31200.0, 9200.0, 860.0]
SIGN = [SIGN_HOLE] * 3 + [SIGN_ELECTRON] * 3


def _sweep(density, mobility, sign, noise=0.0, seed=11, extra=None):
    xx, xy = resistivity(
        FIELDS, density_to_si(density), mobility_to_si(mobility), sign
    )
    xx, xy = resistivity_from_si(xx), resistivity_from_si(xy)
    if extra is not None:
        xx = xx + extra(FIELDS, xx)
    if noise:
        generator = np.random.default_rng(seed)
        xx = xx + generator.normal(scale=noise * np.abs(xx).mean(), size=FIELDS.size)
        xy = xy + generator.normal(scale=noise * np.max(np.abs(xy)), size=FIELDS.size)
    return dataio.TemperatureGroup(
        T_K=5.0, B_T=FIELDS, rhoxx_uohmcm=xx, rhoxy_uohmcm=xy,
        in_fit_window=np.ones(FIELDS.size, dtype=bool),
        n_records_dropped=0, n_mirror_interpolated=0, n_mirror_absent=0,
    )


def _spectrum_of(group, **settings):
    config = cfg.resolve({
        "schema_version": "1.0",
        "columns": {"T": "T(K)", "B": "B(T)", "rhoxx": "a", "rhoxy": "b"},
        "carriers": [
            {"name": "h", "kind": "hole",
             "density": {"init": 1e21, "min": 1e15, "max": 1e23},
             "mobility": {"init": 2000.0, "min": 1.0, "max": 1e6}},
            {"name": "e", "kind": "electron",
             "density": {"init": 1e21, "min": 1e15, "max": 1e23},
             "mobility": {"init": 1000.0, "min": 1.0, "max": 1e6}},
        ],
        "optimization": {"multi_start": 2},
        "spectrum": dict(
            {"enabled": True, "lorentzian_terms": 6, "lorentzian_multi_start": 12,
             "mu_min_cm2Vs": 100.0},
            **settings,
        ),
    })
    dataset = dataio.Dataset(groups=(group,), n_records_dropped=0)
    result = fitting.fit_dataset(dataset, config)
    entry = spectrum.for_temperature(result.fits[0], group, config)
    return entry, config, dataset, result


@pytest.mark.slow
def test_a_sweep_the_model_describes_comes_back_through_it():
    """AC-025 from the good side. Research 003 section 8.2.

    Noiseless, the carriers FR-074 reads off the spectrum reproduce the sweep
    they were made from to well inside the tolerance. This is what makes the
    failures below attributable to the data rather than to the conversion.
    """
    entry, _, _, _ = _spectrum_of(_sweep(DENSITY, MOBILITY, SIGN))
    assert entry.proposal == {"hole": 3, "electron": 3}
    assert entry.roundtrip_rhoxx < 0.02
    assert entry.roundtrip_rhoxy < 0.02


@pytest.mark.slow
def test_the_round_trip_is_reported_per_channel():
    """FR-079. The Hall channel is the one that goes first, so it is separate.

    A peak's density comes from `sigma_xx(0) * S = n q mu` -- the longitudinal
    channel alone. Nothing in that expression holds `rho_xy`, so a single
    combined number would let a large Hall error hide behind a small
    longitudinal one.
    """
    entry, _, _, _ = _spectrum_of(_sweep(DENSITY, MOBILITY, SIGN))
    assert entry.roundtrip_rhoxx == entry.roundtrip_rhoxx   # not NaN
    assert entry.roundtrip_rhoxy == entry.roundtrip_rhoxy
    assert entry.roundtrip == max(entry.roundtrip_rhoxx, entry.roundtrip_rhoxy)


@pytest.mark.slow
def test_a_clean_sweep_raises_no_round_trip_warning():
    entry, _, _, _ = _spectrum_of(_sweep(DENSITY, MOBILITY, SIGN))
    codes = {d.code for d in diagnostics.spectrum_reading((entry,))}
    assert "D_SPECTRUM_ROUNDTRIP" not in codes


# ------------------------- what FR-079 exists for

def _widened(width, n_sub=9):
    """Every carrier replaced by a log-normal cluster of the same first moment.

    Total density and total `n mu` are held fixed, so this changes only the
    *spread* of the mobility distribution and nothing a reader would call the
    carrier set. It is what a band with a distribution of scattering times
    looks like, as opposed to the single scattering time PM-001 assumes.
    """
    density, mobility, sign = [], [], []
    for n0, mu0, s in zip(DENSITY, MOBILITY, SIGN):
        offsets = np.linspace(-2.0, 2.0, n_sub)
        weight = np.exp(-0.5 * offsets**2)
        weight = weight / weight.sum()
        mus = mu0 * np.exp(width * offsets)
        ns = n0 * weight
        ns = ns * (n0 * mu0) / float((ns * mus).sum())
        density.extend(ns)
        mobility.extend(mus)
        sign.extend([s] * n_sub)
    return density, mobility, sign


@pytest.mark.slow
def test_mobility_spread_breaks_the_hall_channel_while_the_extension_fits():
    """Research 003 section 8.3. The reason AC-021 cannot stand in for AC-025.

    A log-width of `0.15` on each carrier leaves the extension fitting to
    better than `1e-3` -- cleaner than any real sweep in this project manages
    -- and puts the Hall channel of the round trip out by tens of percent.
    Every check this feature had before FR-079 reads that sweep as excellent.

    The cause is the peak reader of FR-074: a broadened peak reported as one
    carrier at its centre keeps the first moment `n mu`, and so `sigma_xx(0)`,
    while `rho_xy` is set by the second moment `n mu^2`. Discretising a
    distribution keeps the first and loses the second.
    """
    entry = _spectrum_of(_sweep(*_widened(0.15)))[0]

    # the extension is not merely adequate here, it is excellent ...
    assert entry.extension.max_relative_residual < 1e-3

    # ... and the carriers it leads to do not describe the Hall channel
    assert entry.roundtrip_rhoxy > 0.15
    assert entry.roundtrip_rhoxy > 3.0 * entry.roundtrip_rhoxx, (
        "the failure has to be lopsided: the density of FR-074 is fixed by "
        "sigma_xx(0) alone, so rho_xy is the channel carrying no constraint"
    )

    codes = {d.code for d in diagnostics.spectrum_reading((entry,))}
    assert "D_SPECTRUM_ROUNDTRIP" in codes


@pytest.mark.slow
def test_structure_in_the_residual_is_not_what_breaks_it():
    """The explanation this project tried first, and had to withdraw.

    An oscillatory component is structure by construction -- no sum of
    Lorentzians represents it -- and it is the candidate research 001 Q4
    names. It raises the extension residual well past anything the noise
    produces and leaves the round trip usable. Pinned here because the wrong
    explanation is the intuitive one and would otherwise be rediscovered.
    """
    def oscillation(B_T, rho_xx):
        B = np.asarray(B_T, dtype=float)
        safe = np.where(np.abs(B) < 1.0, np.nan, B)
        return 0.02 * float(np.max(np.abs(rho_xx))) * np.nan_to_num(
            np.sin(2.0 * np.pi * 30.0 / safe)
        )

    noisy = _spectrum_of(_sweep(DENSITY, MOBILITY, SIGN, noise=0.002))[0]
    wavy = _spectrum_of(_sweep(DENSITY, MOBILITY, SIGN, extra=oscillation))[0]

    # far the worse residual of the two ...
    assert wavy.extension.max_relative_residual >         2.0 * noisy.extension.max_relative_residual
    # ... and its round trip is no worse
    assert wavy.roundtrip_rhoxy < 0.05


@pytest.mark.slow
def test_the_warning_names_the_channel_and_its_threshold():
    """FR-048 applies here too: a reader may disagree with the threshold."""
    structured = _spectrum_of(_sweep(*_widened(0.15)))[0]
    found = [d for d in diagnostics.spectrum_reading((structured,))
             if d.code == "D_SPECTRUM_ROUNDTRIP"]
    assert found
    for entry in found:
        assert entry.where["channel"] in ("rhoxx", "rhoxy")
        assert entry.threshold == pytest.approx(0.05)
        assert entry.threshold_source == "AC-025"


@pytest.mark.slow
def test_the_tolerance_is_a_declared_setting():
    group = _sweep(*_widened(0.15))
    strict = _spectrum_of(group, roundtrip_tolerance=1e-6)[0]
    loose = _spectrum_of(group, roundtrip_tolerance=10.0)[0]
    assert "D_SPECTRUM_ROUNDTRIP" in {d.code for d in diagnostics.spectrum_reading((strict,))}
    assert "D_SPECTRUM_ROUNDTRIP" not in {d.code for d in diagnostics.spectrum_reading((loose,))}


@pytest.mark.slow
def test_the_round_trip_file_is_written(tmp_path):
    """The number has to reach a reader, not only a diagnostic. FR-079."""
    import pandas as pd

    from mbfit import report

    group = _sweep(DENSITY, MOBILITY, SIGN)
    entry, _, _, _ = _spectrum_of(group)
    written = report.write_spectrum((entry,), tmp_path)
    path = tmp_path / "spectrum_roundtrip_5K.csv"
    assert path in written and path.exists()

    frame = pd.read_csv(path)
    assert sorted(frame["channel"]) == ["rhoxx", "rhoxy"]
    assert set(frame.columns) >= {"channel", "max_relative_error", "tolerance"}
    row = frame[frame["channel"] == "rhoxy"].iloc[0]
    assert row["max_relative_error"] == pytest.approx(entry.roundtrip_rhoxy)
