"""The inherited prototype as an answer key. Gate 7.

`plan.md` section 4: `legacy/multiband_transport_fitter.py` is not inherited
as code, only as numbers. It has one known defect, the Hall sign of research
2.1, and this test pins the correction as a single deliberate change rather
than leaving open the possibility that something else moved with it.

    rho_xx agrees to 1e-12 relative, unchanged
    rho_xy agrees to 1e-12 relative after negation

The test is deleted when the legacy file is, and not before.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

from mbfit.core.drude import SIGN_ELECTRON, SIGN_HOLE, resistivity
from mbfit.core.units import density_to_si, mobility_to_si, resistivity_from_si

LEGACY = pathlib.Path(__file__).resolve().parent.parent / "legacy" / "multiband_transport_fitter.py"
TOLERANCE = 1e-12


@pytest.fixture(scope="module")
def prototype():
    if not LEGACY.exists():
        pytest.skip("legacy/ has been removed, and so may this test be")
    specification = importlib.util.spec_from_file_location("legacy_prototype", LEGACY)
    module = importlib.util.module_from_spec(specification)
    # Registered before execution: the prototype uses dataclasses under
    # `from __future__ import annotations`, and resolving those annotations
    # needs the module to be findable by name.
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _legacy_resistivity(prototype, B_T, n_cm3, mu_cm2Vs, sign):
    sigma_xx, sigma_xy = prototype.conductivity_model(B_T, n_cm3, mu_cm2Vs, sign)
    return prototype.resistivity_from_conductivity(sigma_xx, sigma_xy)


def _ours(B_T, n_cm3, mu_cm2Vs, sign):
    rho_xx, rho_xy = resistivity(
        B_T, density_to_si(n_cm3), mobility_to_si(mu_cm2Vs), sign
    )
    return resistivity_from_si(rho_xx), resistivity_from_si(rho_xy)


def _worst(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    scale = np.maximum(np.abs(b), np.finfo(float).tiny)
    return float(np.max(np.abs(a - b) / scale))


FIELDS = np.array([-9.0, -3.0, -0.5, 0.5, 3.0, 9.0])

CASES = [
    ("one electron", [1e19], [5000.0], [SIGN_ELECTRON]),
    ("one hole", [1e19], [5000.0], [SIGN_HOLE]),
    ("one of each", [3e18, 1.1e19], [12000.0, 3500.0], [SIGN_ELECTRON, SIGN_HOLE]),
    (
        "two of each",
        [1.46e19, 8.91e20, 8.86e18, 1.01e21],
        [6038.0, 497.0, 6101.0, 265.0],
        [SIGN_ELECTRON, SIGN_ELECTRON, SIGN_HOLE, SIGN_HOLE],
    ),
]


@pytest.mark.parametrize("label,n,mu,sign", CASES, ids=[case[0] for case in CASES])
def test_the_longitudinal_channel_is_unchanged(prototype, label, n, mu, sign):
    theirs = _legacy_resistivity(prototype, FIELDS, n, mu, sign)
    ours = _ours(FIELDS, n, mu, sign)
    assert _worst(ours[0], theirs[0]) < TOLERANCE


@pytest.mark.parametrize("label,n,mu,sign", CASES, ids=[case[0] for case in CASES])
def test_the_hall_channel_agrees_after_negation_and_only_after_it(
    prototype, label, n, mu, sign
):
    theirs = _legacy_resistivity(prototype, FIELDS, n, mu, sign)
    ours = _ours(FIELDS, n, mu, sign)

    assert _worst(ours[1], -np.asarray(theirs[1])) < TOLERANCE
    # And the correction is real, not a rounding difference: without the
    # negation the two disagree by twice the signal.
    assert _worst(ours[1], theirs[1]) > 1.0


def test_the_prototype_is_self_consistent_and_wrong_in_the_documented_way(prototype):
    """One electron at positive field. The whole of research 2.1 in a line."""
    theirs = _legacy_resistivity(prototype, np.array([3.0]), [1e19], [5000.0], [SIGN_ELECTRON])
    ours = _ours(np.array([3.0]), [1e19], [5000.0], [SIGN_ELECTRON])

    assert theirs[1][0] > 0.0    # the prototype calls an electron hole-like
    assert ours[1][0] < 0.0      # PM-001 does not
    assert theirs[0][0] == pytest.approx(ours[0][0], rel=TOLERANCE)


def test_the_conductivity_to_resistivity_round_trip_matches_too(prototype):
    """Both directions, since the prototype cancelled its own sign error."""
    n, mu, sign = [3e18, 1.1e19], [12000.0, 3500.0], [SIGN_ELECTRON, SIGN_HOLE]
    rho_xx, rho_xy = _legacy_resistivity(prototype, FIELDS, n, mu, sign)
    back = prototype.conductivity_from_resistivity(rho_xx, rho_xy)
    forward = prototype.conductivity_model(FIELDS, n, mu, sign)
    assert _worst(back[0], forward[0]) < 1e-10
    assert _worst(back[1], forward[1]) < 1e-10
