"""NR-004 and Constitution Article V: the unit contract, both directions."""

from __future__ import annotations

import numpy as np
import pytest

from mbfit.core import units
from mbfit.core.constants import ELEMENTARY_CHARGE_C as Q

VALUES = np.array([1.0, 1e-4, 3.7e21, 5e3])


@pytest.mark.parametrize(
    "forward,backward",
    [
        (units.density_to_si, units.density_from_si),
        (units.mobility_to_si, units.mobility_from_si),
        (units.resistivity_to_si, units.resistivity_from_si),
    ],
)
def test_every_conversion_round_trips(forward, backward):
    assert np.allclose(backward(forward(VALUES)), VALUES, rtol=1e-15, atol=0.0)
    assert np.allclose(forward(backward(VALUES)), VALUES, rtol=1e-15, atol=0.0)


def test_the_three_factors_are_the_ones_the_contract_names():
    assert units.DENSITY_CM3_TO_SI == 1e6
    assert units.MOBILITY_CM2VS_TO_SI == 1e-4
    assert units.RESISTIVITY_UOHMCM_TO_SI == 1e-8


def test_one_micro_ohm_cm_is_1e_minus_8_ohm_metre():
    """`1e-6 ohm x 1e-2 m`. The factor that appears twice in every round trip."""
    assert units.resistivity_to_si(1.0) == pytest.approx(1e-6 * 1e-2, rel=1e-15)


def test_a_typical_metal_has_a_resistivity_of_order_ten_in_boundary_units():
    """The scale argument of research 3, made into a test.

    `1 / (n q mu)` for a typical metal is a number of order 10 to 100 in
    micro-ohm cm, and of order 1e-8 if the factor above is dropped. That is
    how a lost conversion announces itself here rather than in a fit.
    """
    n_si = units.density_to_si(1e21)
    mu_si = units.mobility_to_si(2000.0)
    rho_boundary = units.resistivity_from_si(1.0 / (n_si * Q * mu_si))
    assert 1.0 < rho_boundary < 1000.0
