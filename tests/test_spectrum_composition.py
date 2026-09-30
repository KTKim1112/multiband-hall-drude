"""T1305b — what the spectrum must not be combined with. FR-078.

Research 002 section 4 gives a test that rejects one non-circular orbit read as
several carriers. It works on carriers a fit returned. Applied instead to the
peaks a smoothed inversion returns, it clears exactly the case it was built to
catch, because the smoothing moves the ratios it depends on.

That is not a defect in either tool. It is a defect in composing them, and it
is invisible from either requirement alone, so it is pinned here.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit import config as cfg
from mbfit import dataio, fitting, spectrum
from mbfit.core import harmonics
from mbfit.core.drude import SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si, resistivity_from_si

FIELDS = np.round(np.linspace(-9.0, 9.0, 121), 6)

# One orbit at 12000 cm^2/Vs through four cyclotron harmonics, weights falling.
ORBIT_MOBILITY = 12000.0
HARMONIC_MOBILITY = [ORBIT_MOBILITY / m for m in (1, 2, 3, 4)]
HARMONIC_DENSITY = [6.0e20, 2.0e20, 8.0e19, 4.0e19]


def _spectrum_of(density, mobility, sign):
    xx, xy = resistivity(FIELDS, density_to_si(density), mobility_to_si(mobility), sign)
    group = dataio.TemperatureGroup(
        T_K=5.0, B_T=FIELDS,
        rhoxx_uohmcm=resistivity_from_si(xx), rhoxy_uohmcm=resistivity_from_si(xy),
        in_fit_window=np.ones(FIELDS.size, dtype=bool),
        n_records_dropped=0, n_mirror_interpolated=0, n_mirror_absent=0,
    )
    config = cfg.resolve({
        "schema_version": "1.0",
        "columns": {"T": "T(K)", "B": "B(T)", "rhoxx": "a", "rhoxy": "b"},
        "carriers": [{
            "name": "h", "kind": "hole",
            "density": {"init": 1e21, "min": 1e15, "max": 1e23},
            "mobility": {"init": 5000.0, "min": 1.0, "max": 1e6},
        }],
        "optimization": {"multi_start": 4},
        "spectrum": {"enabled": True, "lorentzian_terms": 6,
                     "lorentzian_multi_start": 12},
    })
    dataset = dataio.Dataset(groups=(group,), n_records_dropped=0)
    result = fitting.fit_dataset(dataset, config)
    return spectrum.for_temperature(result.fits[0], group, config)


@pytest.mark.slow
def test_FR078_the_ladder_test_clears_what_the_spectrum_returns():
    """The reason FR-078 exists, measured on both sides of the composition."""
    weights = np.asarray(HARMONIC_DENSITY, dtype=float)
    mobilities = np.asarray(HARMONIC_MOBILITY, dtype=float)

    # the test works on what was generated
    generated = harmonics.verdict(weights, mobilities, np.ones(4), 0.05)
    assert generated["is_ladder"]
    assert list(np.round(generated["ratios"], 3)) == [1.0, 2.0, 3.0, 4.0]

    # and clears what the spectrum makes of the same data
    entry = _spectrum_of(HARMONIC_DENSITY, HARMONIC_MOBILITY, [SIGN_HOLE] * 4)
    found = spectrum.carriers_from(entry.branch("hole"), entry.sigma_xx_zero)
    assert len(found) >= 2

    recovered_mu = np.array([item["mobility_cm2Vs"] for item in found])
    recovered_weight = np.array([item["weight"] for item in found])
    after = harmonics.verdict(
        recovered_weight, recovered_mu, np.ones(recovered_mu.size), 0.05
    )
    assert not after["is_ladder"]
    assert "consecutive_integers" in after["failed"]

    # the fundamental survives, which is what makes the wrong answer plausible
    assert recovered_mu.max() == pytest.approx(ORBIT_MOBILITY, rel=0.05)


@pytest.mark.slow
def test_an_all_hole_system_returns_no_electron():
    """AC-019, absolute rather than relative. Research 003 section 7.1.

    Comparing a local maximum with the largest in its own branch says nothing
    when the branch is empty. The measured failure was an electron reported at
    118571 cm^2/Vs carrying 0.000 % of the spectrum, in a branch that had
    correctly come back at zero.
    """
    entry = _spectrum_of(HARMONIC_DENSITY, HARMONIC_MOBILITY, [SIGN_HOLE] * 4)

    assert entry.proposal["electron"] == 0
    assert entry.proposal["hole"] >= 2
    assert entry.branch("electron").density.sum() < 1e-6
    assert spectrum.carriers_from(entry.branch("electron"), entry.sigma_xx_zero) == []
