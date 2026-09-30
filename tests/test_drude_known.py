"""Constitution Article II: the model against known answers.

These are K1 to K8 of research 2.3, the list that exists because a wrong fit
does not crash. It returns a plausible number, and this project has already
seen that happen: the inherited prototype reproduced `rho_xx = 1/(n q mu)`
exactly while returning `rho_xy` with the wrong sign, changing nothing in any
residual and inverting the electron/hole conclusion.

Tolerances are the disagreements measured on 2026-08-26, rounded up. Three
are finite-difference or finite-field approximations rather than identities
and are looser for that reason, which is stated where it applies.
"""

from __future__ import annotations

import numpy as np
import pytest

from mbfit.core.constants import ELEMENTARY_CHARGE_C as Q
from mbfit.core.drude import (
    SIGN_ELECTRON,
    SIGN_HOLE,
    conductivity_from_resistivity,
    conductivity_tensor,
    resistivity,
    resistivity_from_conductivity,
)
from mbfit.core.units import density_to_si, mobility_to_si

EXACT = 1e-13  # identities; measured at 4e-16
FIELDS = np.array([-9.0, -3.0, -0.5, 0.0, 0.5, 3.0, 9.0])


def _relative(actual, expected):
    actual = np.asarray(actual, dtype=float)
    expected = np.asarray(expected, dtype=float)
    scale = np.maximum(np.abs(expected), np.finfo(float).tiny)
    return float(np.max(np.abs(actual - expected) / scale))


# --------------------------------------------------------------- one carrier

@pytest.mark.parametrize("kind_sign", [SIGN_ELECTRON, SIGN_HOLE])
def test_K1_single_carrier_longitudinal_is_field_independent(kind_sign):
    n = density_to_si(1e19)
    mu = mobility_to_si(5000.0)
    rho_xx, _ = resistivity(FIELDS, [n], [mu], [kind_sign])
    expected = np.full(FIELDS.shape, 1.0 / (n * Q * mu))
    assert _relative(rho_xx, expected) < EXACT


@pytest.mark.parametrize("kind_sign", [SIGN_ELECTRON, SIGN_HOLE])
def test_K2_single_carrier_hall_is_B_over_n_q_signed(kind_sign):
    n = density_to_si(1e19)
    mu = mobility_to_si(5000.0)
    _, rho_xy = resistivity(FIELDS, [n], [mu], [kind_sign])
    expected = FIELDS / (n * kind_sign * Q)
    assert _relative(rho_xy, expected) < EXACT


def test_PM001_sign_of_the_hall_signal():
    """The whole point of research 2.1, asserted directly and unmissably.

    At positive field a single electron band gives negative `rho_xy` and a
    single hole band gives positive `rho_xy`.
    """
    n = density_to_si(1e19)
    mu = mobility_to_si(5000.0)
    _, electron = resistivity([3.0], [n], [mu], [SIGN_ELECTRON])
    _, hole = resistivity([3.0], [n], [mu], [SIGN_HOLE])
    assert electron[0] < 0.0
    assert hole[0] > 0.0
    assert electron[0] == pytest.approx(-hole[0], rel=EXACT)


def test_PM002_polarity_reverses_the_hall_signal_and_leaves_the_rest():
    n = density_to_si(1e19)
    mu = mobility_to_si(5000.0)
    rho_xx, rho_xy = resistivity(FIELDS, [n], [mu], [SIGN_ELECTRON], hall_polarity=1.0)
    flipped_xx, flipped_xy = resistivity(
        FIELDS, [n], [mu], [SIGN_ELECTRON], hall_polarity=-1.0
    )
    assert _relative(flipped_xx, rho_xx) < EXACT
    assert _relative(flipped_xy, -rho_xy) < EXACT


# --------------------------------------------------------------- two carriers

def _two_band():
    n_e = density_to_si(3e18)
    n_h = density_to_si(1.1e19)
    mu_e = mobility_to_si(12000.0)
    mu_h = mobility_to_si(3500.0)
    return n_e, n_h, mu_e, mu_h


def _two_band_arrays():
    n_e, n_h, mu_e, mu_h = _two_band()
    return [n_e, n_h], [mu_e, mu_h], [SIGN_ELECTRON, SIGN_HOLE]


def test_K3_two_band_longitudinal_closed_form():
    n_e, n_h, mu_e, mu_h = _two_band()
    n, mu, sign = _two_band_arrays()
    rho_xx, _ = resistivity(FIELDS, n, mu, sign)

    a = n_e * mu_e + n_h * mu_h
    delta_n = n_h - n_e
    denominator = Q * (a**2 + (delta_n * mu_e * mu_h * FIELDS) ** 2)
    expected = (a + (n_e * mu_h + n_h * mu_e) * mu_e * mu_h * FIELDS**2) / denominator
    assert _relative(rho_xx, expected) < EXACT


def test_K4_two_band_hall_closed_form():
    n_e, n_h, mu_e, mu_h = _two_band()
    n, mu, sign = _two_band_arrays()
    _, rho_xy = resistivity(FIELDS, n, mu, sign)

    a = n_e * mu_e + n_h * mu_h
    delta_n = n_h - n_e
    denominator = Q * (a**2 + (delta_n * mu_e * mu_h * FIELDS) ** 2)
    expected = (
        FIELDS
        * ((n_h * mu_h**2 - n_e * mu_e**2) + delta_n * (mu_e * mu_h) ** 2 * FIELDS**2)
        / denominator
    )
    assert _relative(rho_xy, expected) < EXACT


def test_K5_low_field_hall_coefficient():
    """A finite difference, so 1e-9 rather than machine precision."""
    n_e, n_h, mu_e, mu_h = _two_band()
    n, mu, sign = _two_band_arrays()
    small = np.array([1e-6, 2e-6])
    _, rho_xy = resistivity(small, n, mu, sign)

    measured_slope = (rho_xy[1] - rho_xy[0]) / (small[1] - small[0])
    a = n_e * mu_e + n_h * mu_h
    expected = (n_h * mu_h**2 - n_e * mu_e**2) / (Q * a**2)
    assert _relative(measured_slope, expected) < 1e-9


def test_K8_high_field_hall_approaches_the_uncompensated_limit():
    """A limit approached, not reached. Measured 7e-8 at 1e4 T."""
    n_e, n_h, _, _ = _two_band()
    n, mu, sign = _two_band_arrays()
    huge = np.array([1e4])
    _, rho_xy = resistivity(huge, n, mu, sign)
    expected = huge / (Q * (n_h - n_e))
    assert _relative(rho_xy, expected) < 1e-6


# ----------------------------------------------------- compensated semimetal

def _compensated():
    n = density_to_si(5e18)
    mu_e = mobility_to_si(12000.0)
    mu_h = mobility_to_si(3500.0)
    return n, mu_e, mu_h


def test_K6_compensated_magnetoresistance_is_quadratic_and_unsaturating():
    n, mu_e, mu_h = _compensated()
    fields = np.array([0.0, 1.0, 3.0, 9.0, 30.0])
    rho_xx, _ = resistivity(fields, [n, n], [mu_e, mu_h], [SIGN_ELECTRON, SIGN_HOLE])
    expected = 1.0 + mu_e * mu_h * fields**2
    assert _relative(rho_xx / rho_xx[0], expected) < EXACT


def test_K7_compensated_hall_is_exactly_linear_and_does_not_vanish():
    """It vanishes only when the two mobilities are equal.

    Recorded because an earlier draft of research 2.3 claimed the compensated
    Hall signal is zero. It is a straight line of slope
    `(mu_h - mu_e) / (q n (mu_e + mu_h))`.
    """
    n, mu_e, mu_h = _compensated()
    fields = np.array([0.0, 1.0, 3.0, 9.0, 30.0])
    _, rho_xy = resistivity(fields, [n, n], [mu_e, mu_h], [SIGN_ELECTRON, SIGN_HOLE])
    expected = fields * (mu_h - mu_e) / (Q * n * (mu_e + mu_h))
    assert _relative(rho_xy, expected) < EXACT
    assert abs(rho_xy[-1]) > 0.0

    _, equal_mobility = resistivity(
        fields, [n, n], [mu_e, mu_e], [SIGN_ELECTRON, SIGN_HOLE]
    )
    assert np.max(np.abs(equal_mobility)) < 1e-30


# ------------------------------------------------------------- tensor inverse

def test_conductivity_and_resistivity_are_inverse_for_either_polarity():
    n, mu, sign = _two_band_arrays()
    for polarity in (1.0, -1.0):
        sigma_xx, sigma_xy = conductivity_tensor(FIELDS, n, mu, sign)
        rho_xx, rho_xy = resistivity_from_conductivity(sigma_xx, sigma_xy, polarity)
        back_xx, back_xy = conductivity_from_resistivity(rho_xx, rho_xy, polarity)
        assert _relative(back_xx, sigma_xx) < EXACT
        assert _relative(back_xy, sigma_xy) < EXACT


def test_carriers_add_in_conductivity_and_not_in_resistivity():
    """Why a multiband fit is not a sum of single-band fits. Research 2.2."""
    n, mu, sign = _two_band_arrays()
    together = conductivity_tensor(FIELDS, n, mu, sign)
    first = conductivity_tensor(FIELDS, n[:1], mu[:1], sign[:1])
    second = conductivity_tensor(FIELDS, n[1:], mu[1:], sign[1:])
    assert _relative(together[0], first[0] + second[0]) < EXACT
    assert _relative(together[1], first[1] + second[1]) < EXACT

    rho_together, _ = resistivity(FIELDS, n, mu, sign)
    rho_first, _ = resistivity(FIELDS, n[:1], mu[:1], sign[:1])
    rho_second, _ = resistivity(FIELDS, n[1:], mu[1:], sign[1:])
    assert np.max(np.abs(rho_together - (rho_first + rho_second))) > 0.0


def test_E_FIT_SINGULAR_when_the_tensor_cannot_be_inverted():
    """Both conductivities zero leaves nothing to invert.

    Unreachable from a fit, since NR-001 keeps every density and mobility
    positive, but the branch exists so that a caller bypassing that gets a
    code rather than a NaN that travels.
    """
    from mbfit.core.errors import MbfitError

    with pytest.raises(MbfitError, match="E_FIT_SINGULAR"):
        resistivity_from_conductivity(np.zeros(3), np.zeros(3))
    with pytest.raises(MbfitError, match="E_FIT_SINGULAR"):
        conductivity_from_resistivity(np.zeros(3), np.zeros(3))
